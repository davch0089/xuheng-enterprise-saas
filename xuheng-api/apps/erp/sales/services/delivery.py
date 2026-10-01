"""销售出库单保存、库存过账、成本和应收联动服务。"""

import json
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, false, select

from apps.erp.common import COST, MONEY, QTY, quantize
from apps.erp.common.settlement import calculate_document_settlement
from apps.erp.inventory.services.stock import (
    MovementType,
    PostingRequest,
    StockMovement,
    StockPostingEngine,
)
from apps.erp.master import models as master_models
from core.exception import CustomException
from apps.erp.finance.services.period import AccountingPeriodService

from .. import models, schemas
from .batch_allocation import SalesBatchAllocator
from .common import SalesServiceSupport
from .receivable import ReceivableService
from .reservation import StockReservationService


class SalesDeliveryService(SalesServiceSupport):
    """负责销售出库草稿、订单履约、库存成本和应收确认。"""

    def __init__(self, db, user_id: int | None = None):
        """绑定当前事务并初始化关联领域服务。"""

        self.db = db
        self.user_id = user_id
        self.reservations = StockReservationService(db)
        self.receivables = ReceivableService(db, user_id)

    async def save(self, data: schemas.SalesDeliveryInput, delivery_id: int | None = None):
        """新增或修改草稿销售出库单并校验订单剩余可交数量。"""

        await AccountingPeriodService(self.db, self.user_id).ensure_open(data.business_date, "新增或修改销售出库单")

        prepared = await self.prepare_lines(
            data,
            tracking_required=True,
            require_batch=data.batch_selection_mode == "manual",
        )
        if data.batch_selection_mode == "auto":
            prepared = await SalesBatchAllocator(self.db).allocate(prepared, data.business_date)
        order = await self._validate_order(data, prepared)
        if delivery_id:
            delivery = await self._lock(delivery_id)
            if delivery.status != "draft":
                raise CustomException("只有草稿销售出库单可以修改")
            await self.db.execute(
                delete(models.ErpSalesDeliveryLine).where(
                    models.ErpSalesDeliveryLine.delivery_id == delivery_id
                )
            )
            if data.delivery_no and data.delivery_no != delivery.delivery_no:
                await self._ensure_number(data.delivery_no, delivery_id)
                delivery.delivery_no = data.delivery_no
        else:
            number = data.delivery_no or await self.next_document_no(
                "sales_delivery", "SD", data.business_date
            )
            await self._ensure_number(number)
            delivery = models.ErpSalesDelivery(delivery_no=number, created_by_id=self.user_id)
            self.db.add(delivery)
        for field in (
            "business_date",
            "customer_id",
            "warehouse_id",
            "order_id",
            "employee_id",
            "delivery_address",
            "batch_selection_mode",
            "settlement_method_id",
            "fund_account_id",
            "remark",
        ):
            setattr(delivery, field, getattr(data, field))
        customer = await self.db.get(master_models.ErpCustomer, data.customer_id)
        delivery.due_date = data.due_date or data.business_date + timedelta(
            days=customer.payment_days or 0
        )
        totals = self.totals(prepared)
        settlement = calculate_document_settlement(
            totals["payable_amount"],
            data.settlement_discount_rate,
            data.rounding_amount,
            data.current_payment_amount,
        )
        totals["payable_amount"] = settlement["settlement_amount"]
        for field, value in {**totals, **settlement}.items():
            setattr(delivery, field, value)
        delivery.total_cost = 0
        delivery.gross_profit = 0
        await self.db.flush()
        for line in prepared:
            serial_numbers = line.pop("serial_numbers")
            self.db.add(
                models.ErpSalesDeliveryLine(
                    delivery_id=delivery.id,
                    serial_numbers=(
                        json.dumps(serial_numbers, ensure_ascii=False) if serial_numbers else None
                    ),
                    unit_cost=0,
                    cost_amount=0,
                    returned_quantity=0,
                    **line,
                )
            )
        await self.db.flush()
        return await self.detail(delivery.id)

    async def approve(self, delivery_id: int):
        """审核销售出库并联动预留释放、库存、成本和应收。"""

        delivery = await self._lock(delivery_id)
        if delivery.status != "draft":
            raise CustomException("只有草稿销售出库单可以审核")
        lines = await self._lines(delivery.id, lock=True)
        if not lines:
            raise CustomException("销售出库单没有商品明细")
        order_lines = {}
        if delivery.order_id:
            order = await self.db.scalar(
                select(models.ErpSalesOrder)
                .where(models.ErpSalesOrder.id == delivery.order_id)
                .with_for_update()
            )
            order_lines = {
                item.id: item
                for item in (
                    await self.db.scalars(
                        select(models.ErpSalesOrderLine)
                        .where(models.ErpSalesOrderLine.order_id == delivery.order_id)
                        .with_for_update()
                    )
                ).all()
            }
            for line in lines:
                order_line = order_lines.get(line.order_line_id)
                if order_line is None:
                    raise CustomException("销售出库明细缺少对应订单行")
                await self.reservations.release_for_delivery(
                    order_line.id, Decimal(line.base_quantity)
                )
                order_line.delivered_quantity = quantize(
                    Decimal(order_line.delivered_quantity) + Decimal(line.base_quantity), QTY
                )
        now = datetime.now()
        version = delivery.posting_version + 1
        movements = tuple(
            StockMovement(
                movement_type=MovementType.SALE_OUT,
                business_line_id=line.id,
                movement_role="sales_delivery",
                product_id=line.product_id,
                warehouse_id=line.warehouse_id,
                quantity=Decimal(line.base_quantity),
                batch_no=line.batch_no,
                serial_numbers=tuple(json.loads(line.serial_numbers) if line.serial_numbers else []),
            )
            for line in lines
        )
        ledgers = await StockPostingEngine(self.db).post(
            PostingRequest(
                source_type="sales_delivery",
                source_id=delivery.id,
                source_no=delivery.delivery_no,
                posting_version=version,
                movements=movements,
                occurred_at=datetime.combine(delivery.business_date, now.time()),
                operator_id=self.user_id,
            )
        )
        ledger_map = {item.business_line_id: item for item in ledgers}
        total_cost = Decimal("0")
        for line in lines:
            ledger = ledger_map[line.id]
            line.cost_amount = abs(Decimal(ledger.amount))
            line.unit_cost = quantize(
                Decimal(line.cost_amount) / Decimal(line.base_quantity), COST
            )
            total_cost += Decimal(line.cost_amount)
        delivery.total_cost = quantize(total_cost, MONEY)
        delivery.gross_profit = quantize(
            Decimal(delivery.total_amount)
            - Decimal(delivery.settlement_discount_amount)
            - Decimal(delivery.rounding_amount)
            - Decimal(delivery.total_cost),
            MONEY,
        )
        delivery.status = "approved"
        delivery.posting_version = version
        delivery.approved_by_id = self.user_id
        delivery.approved_at = now
        if delivery.order_id:
            self._refresh_order_status(order, list(order_lines.values()))
        await self.db.flush()
        receivable = await self.receivables.recognize_delivery(delivery)
        if Decimal(delivery.current_payment_amount) > 0:
            if not delivery.fund_account_id:
                raise CustomException("填写本次收款后必须选择收款账户")
            from .receipt import SalesReceiptService

            receipt_service = SalesReceiptService(self.db, self.user_id)
            auto_receipt = await receipt_service.save(
                schemas.SalesReceiptInput(
                    receipt_date=delivery.business_date,
                    customer_id=delivery.customer_id,
                    settlement_method_id=delivery.settlement_method_id,
                    fund_account_id=delivery.fund_account_id,
                    amount=delivery.current_payment_amount,
                    allocations=[
                        schemas.ReceiptAllocationInput(
                            receivable_id=receivable.id,
                            amount=delivery.current_payment_amount,
                        )
                    ],
                    remark=f"由销售出库 {delivery.delivery_no} 审核自动生成",
                )
            )
            await receipt_service.approve(auto_receipt["id"])
            delivery.linked_receipt_id = auto_receipt["id"]
            await self.db.flush()
        return await self.detail(delivery.id)

    async def unapprove(self, delivery_id: int):
        """冲销没有退货和收款的销售出库并恢复订单预留。"""

        delivery = await self._lock(delivery_id)
        if delivery.status != "approved":
            raise CustomException("只有已审核销售出库单可以反审核")
        lines = await self._lines(delivery.id, lock=True)
        if any(Decimal(line.returned_quantity) for line in lines):
            raise CustomException("销售出库已发生退货，不能反审核")
        if delivery.linked_receipt_id:
            from .receipt import SalesReceiptService

            receipt_service = SalesReceiptService(self.db, self.user_id)
            linked_receipt = await self.db.get(models.ErpSalesReceipt, delivery.linked_receipt_id)
            if linked_receipt and not linked_receipt.is_delete:
                if linked_receipt.status == "approved":
                    await receipt_service.unapprove(linked_receipt.id)
                await receipt_service.delete([linked_receipt.id])
            delivery.linked_receipt_id = None
        await self.receivables.reverse_delivery(delivery)
        await StockPostingEngine(self.db).reverse(
            source_type="sales_delivery",
            source_id=delivery.id,
            posting_version=delivery.posting_version,
            source_no=delivery.delivery_no,
            operator_id=self.user_id,
        )
        if delivery.order_id:
            order = await self.db.scalar(
                select(models.ErpSalesOrder)
                .where(models.ErpSalesOrder.id == delivery.order_id)
                .with_for_update()
            )
            order_lines = {
                item.id: item
                for item in (
                    await self.db.scalars(
                        select(models.ErpSalesOrderLine)
                        .where(models.ErpSalesOrderLine.order_id == delivery.order_id)
                        .with_for_update()
                    )
                ).all()
            }
            for line in lines:
                order_line = order_lines[line.order_line_id]
                order_line.delivered_quantity = quantize(
                    Decimal(order_line.delivered_quantity) - Decimal(line.base_quantity), QTY
                )
                await self.reservations.restore_from_delivery(
                    order_line.id, Decimal(line.base_quantity)
                )
            self._refresh_order_status(order, list(order_lines.values()))
        delivery.status = "draft"
        delivery.approved_by_id = None
        delivery.approved_at = None
        delivery.total_cost = 0
        delivery.gross_profit = 0
        for line in lines:
            line.unit_cost = 0
            line.cost_amount = 0
        await self.db.flush()
        return await self.detail(delivery.id)

    async def delete(self, ids: list[int]):
        """批量删除草稿销售出库单。"""

        docs = list(
            (
                await self.db.scalars(
                    select(models.ErpSalesDelivery).where(
                        models.ErpSalesDelivery.id.in_(ids),
                        models.ErpSalesDelivery.is_delete == false(),
                    )
                )
            ).all()
        )
        if len(docs) != len(set(ids)) or any(item.status != "draft" for item in docs):
            raise CustomException("只能删除存在的草稿销售出库单")
        await self.db.execute(
            delete(models.ErpSalesDeliveryLine).where(
                models.ErpSalesDeliveryLine.delivery_id.in_(ids)
            )
        )
        await self.db.execute(
            delete(models.ErpSalesDelivery).where(models.ErpSalesDelivery.id.in_(ids))
        )

    async def detail(self, delivery_id: int):
        """返回销售出库单及其批次、序列号和成本明细。"""

        delivery = await self.db.scalar(
            select(models.ErpSalesDelivery).where(
                models.ErpSalesDelivery.id == delivery_id,
                models.ErpSalesDelivery.is_delete == false(),
            )
        )
        if delivery is None:
            raise CustomException("销售出库单不存在")
        result = {key: getattr(delivery, key) for key in delivery.get_column_attrs()}
        if delivery.linked_receipt_id:
            linked_receipt = await self.db.get(models.ErpSalesReceipt, delivery.linked_receipt_id)
            result["linked_receipt_no"] = (
                linked_receipt.receipt_no if linked_receipt and not linked_receipt.is_delete else None
            )
        result["lines"] = []
        lines = list(await self._lines(delivery_id))
        products = await self.product_views(line.product_id for line in lines)
        for line in lines:
            item = {key: getattr(line, key) for key in line.get_column_attrs()}
            item["serial_numbers"] = json.loads(line.serial_numbers) if line.serial_numbers else []
            item["product"] = products.get(line.product_id)
            result["lines"].append(item)
        return jsonable_encoder(result)

    async def _validate_order(self, data, prepared):
        """校验出库单引用订单的客户、状态和剩余可交数量。"""

        if not data.order_id:
            if any(line["order_line_id"] for line in prepared):
                raise CustomException("无订单出库不能填写订单明细ID")
            return None
        order = await self.db.scalar(
            select(models.ErpSalesOrder).where(
                models.ErpSalesOrder.id == data.order_id,
                models.ErpSalesOrder.is_delete == false(),
            )
        )
        if order is None or order.status not in ("approved", "partial"):
            raise CustomException("销售订单不存在或状态不允许出库")
        if order.customer_id != data.customer_id:
            raise CustomException("销售出库客户与订单客户不一致")
        order_lines = {
            item.id: item
            for item in (
                await self.db.scalars(
                    select(models.ErpSalesOrderLine).where(
                        models.ErpSalesOrderLine.order_id == order.id
                    )
                )
            ).all()
        }
        used_quantity: dict[int, Decimal] = {}
        for line in prepared:
            order_line = order_lines.get(line["order_line_id"])
            if order_line is None:
                raise CustomException("销售出库订单明细无效")
            if order_line.product_id != line["product_id"]:
                raise CustomException("销售出库商品与订单明细不一致")
            remaining = Decimal(order_line.base_quantity) - Decimal(order_line.delivered_quantity)
            used_quantity[order_line.id] = used_quantity.get(order_line.id, Decimal(0)) + Decimal(
                line["base_quantity"]
            )
            if used_quantity[order_line.id] > remaining:
                raise CustomException("销售出库数量超过订单未交数量")
        return order

    async def _lock(self, delivery_id: int):
        """锁定销售出库单表头。"""

        delivery = await self.db.scalar(
            select(models.ErpSalesDelivery)
            .where(
                models.ErpSalesDelivery.id == delivery_id,
                models.ErpSalesDelivery.is_delete == false(),
            )
            .with_for_update()
        )
        if delivery is None:
            raise CustomException("销售出库单不存在")
        return delivery

    async def _lines(self, delivery_id: int, lock: bool = False):
        """读取销售出库明细并可选加锁。"""

        sql = select(models.ErpSalesDeliveryLine).where(
            models.ErpSalesDeliveryLine.delivery_id == delivery_id
        ).order_by(models.ErpSalesDeliveryLine.line_no)
        if lock:
            sql = sql.with_for_update()
        return list((await self.db.scalars(sql)).all())

    async def _ensure_number(self, number: str, exclude_id: int | None = None):
        """确保销售出库单号唯一。"""

        conditions = [models.ErpSalesDelivery.delivery_no == number]
        if exclude_id:
            conditions.append(models.ErpSalesDelivery.id != exclude_id)
        if await self.db.scalar(select(models.ErpSalesDelivery.id).where(*conditions)):
            raise CustomException("销售出库单号已存在")

    @staticmethod
    def _refresh_order_status(order, lines):
        """根据累计出库量刷新订单履约状态。"""

        delivered = sum((Decimal(line.delivered_quantity) for line in lines), Decimal(0))
        ordered = sum((Decimal(line.base_quantity) for line in lines), Decimal(0))
        order.status = "completed" if delivered >= ordered else "partial" if delivered else "approved"
