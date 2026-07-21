"""销售退货保存、原单校验、回库和红字应收服务。"""

import json
from datetime import datetime
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, false, select

from apps.erp.common import COST, MONEY, QTY, quantize
from apps.erp.inventory.services.inbound import InventoryService
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
from .common import SalesServiceSupport
from .receivable import ReceivableService


class SalesReturnService(SalesServiceSupport):
    """负责按原销售出库创建退货、按原成本回库并冲减应收。"""

    def __init__(self, db, user_id: int | None = None):
        """绑定当前事务和操作人。"""

        self.db = db
        self.user_id = user_id
        self.receivables = ReceivableService(db, user_id)

    async def save(self, data: schemas.SalesReturnInput, return_id: int | None = None):
        """新增或修改草稿退货单并校验原出库可退数量。"""

        await AccountingPeriodService(self.db, self.user_id).ensure_open(data.business_date, "新增或修改销售退货单")

        delivery = await self.db.scalar(
            select(models.ErpSalesDelivery).where(
                models.ErpSalesDelivery.id == data.delivery_id,
                models.ErpSalesDelivery.status == "approved",
                models.ErpSalesDelivery.is_delete == false(),
            )
        )
        if delivery is None or delivery.customer_id != data.customer_id:
            raise CustomException("原销售出库不存在、未审核或客户不一致")
        source_lines = {
            item.id: item
            for item in (
                await self.db.scalars(
                    select(models.ErpSalesDeliveryLine).where(
                        models.ErpSalesDeliveryLine.delivery_id == delivery.id
                    )
                )
            ).all()
        }
        unit_service = InventoryService(self.db)
        prepared = []
        for index, input_line in enumerate(data.lines, 1):
            source = source_lines.get(input_line.delivery_line_id)
            if source is None:
                raise CustomException(f"第{index}行原出库明细无效")
            units = {
                item["unit_id"]: item
                for item in await unit_service.product_units(
                    await self.db.get(master_models.ErpProduct, source.product_id)
                )
            }
            unit_id = input_line.unit_id or source.unit_id
            unit = units.get(unit_id)
            if unit is None:
                raise CustomException(f"第{index}行退货单位无效")
            quantity = quantize(Decimal(input_line.quantity), QTY)
            base_quantity = quantize(quantity * Decimal(unit["to_base_rate"]), QTY)
            remaining = quantize(
                Decimal(source.base_quantity) - Decimal(source.returned_quantity), QTY
            )
            if base_quantity > remaining:
                raise CustomException(f"第{index}行退货数量超过原出库可退数量")
            ratio = base_quantity / Decimal(source.base_quantity)
            amount = quantize(Decimal(source.amount) * ratio, MONEY)
            discount_amount = quantize(Decimal(source.discount_amount) * ratio, MONEY)
            tax_amount = quantize(Decimal(source.tax_amount) * ratio, MONEY)
            inclusive = quantize(Decimal(source.tax_inclusive_amount) * ratio, MONEY)
            cost_amount = quantize(Decimal(source.cost_amount) * ratio, MONEY)
            source_serials = set(json.loads(source.serial_numbers) if source.serial_numbers else [])
            serials = list(input_line.serial_numbers)
            if source_serials:
                if len(serials) != int(base_quantity) or not set(serials).issubset(source_serials):
                    raise CustomException(f"第{index}行退货序列号必须来自原出库明细")
            prepared.append(
                {
                    "line_no": index,
                    "delivery_line_id": source.id,
                    "product_id": source.product_id,
                    "warehouse_id": input_line.warehouse_id or data.warehouse_id,
                    "unit_id": unit_id,
                    "unit_to_base_rate": Decimal(unit["to_base_rate"]),
                    "quantity": quantity,
                    "base_quantity": base_quantity,
                    "unit_price": source.unit_price,
                    "discount_rate": source.discount_rate,
                    "amount": amount,
                    "discount_amount": discount_amount,
                    "tax_rate": source.tax_rate,
                    "tax_amount": tax_amount,
                    "tax_inclusive_amount": inclusive,
                    "batch_no": input_line.batch_no or source.batch_no,
                    "serial_numbers": serials,
                    "unit_cost": source.unit_cost,
                    "cost_amount": cost_amount,
                    "remark": input_line.remark,
                }
            )
        if return_id:
            sales_return = await self._lock(return_id)
            if sales_return.status != "draft":
                raise CustomException("只有草稿销售退货单可以修改")
            await self.db.execute(
                delete(models.ErpSalesReturnLine).where(
                    models.ErpSalesReturnLine.return_id == return_id
                )
            )
        else:
            number = data.return_no or await self.next_document_no(
                "sales_return", "SR", data.business_date
            )
            if await self.db.scalar(
                select(models.ErpSalesReturn.id).where(models.ErpSalesReturn.return_no == number)
            ):
                raise CustomException("销售退货单号已存在")
            sales_return = models.ErpSalesReturn(
                return_no=number, created_by_id=self.user_id
            )
            self.db.add(sales_return)
        for field in (
            "business_date",
            "delivery_id",
            "customer_id",
            "warehouse_id",
            "employee_id",
            "remark",
        ):
            setattr(sales_return, field, getattr(data, field))
        sales_return.delivery_address = delivery.delivery_address
        for field, value in self.totals(prepared).items():
            setattr(sales_return, field, value)
        sales_return.total_cost = quantize(
            sum((Decimal(line["cost_amount"]) for line in prepared), Decimal(0)), MONEY
        )
        await self.db.flush()
        for line in prepared:
            serials = line.pop("serial_numbers")
            self.db.add(
                models.ErpSalesReturnLine(
                    return_id=sales_return.id,
                    serial_numbers=json.dumps(serials, ensure_ascii=False) if serials else None,
                    **line,
                )
            )
        await self.db.flush()
        return await self.detail(sales_return.id)

    async def approve(self, return_id: int):
        """审核退货单并按原出库成本回库、冲减客户应收。"""

        sales_return = await self._lock(return_id)
        if sales_return.status != "draft":
            raise CustomException("只有草稿销售退货单可以审核")
        delivery = await self.db.scalar(
            select(models.ErpSalesDelivery)
            .where(models.ErpSalesDelivery.id == sales_return.delivery_id)
            .with_for_update()
        )
        lines = await self._lines(return_id, lock=True)
        source_lines = {
            item.id: item
            for item in (
                await self.db.scalars(
                    select(models.ErpSalesDeliveryLine)
                    .where(models.ErpSalesDeliveryLine.delivery_id == delivery.id)
                    .with_for_update()
                )
            ).all()
        }
        for line in lines:
            source = source_lines[line.delivery_line_id]
            if Decimal(source.returned_quantity) + Decimal(line.base_quantity) > Decimal(
                source.base_quantity
            ):
                raise CustomException("退货数量超过原出库可退数量")
        now = datetime.now()
        version = sales_return.posting_version + 1
        await StockPostingEngine(self.db).post(
            PostingRequest(
                source_type="sales_return",
                source_id=sales_return.id,
                source_no=sales_return.return_no,
                posting_version=version,
                movements=tuple(
                    StockMovement(
                        movement_type=MovementType.SALE_RETURN,
                        business_line_id=line.id,
                        movement_role="sales_return",
                        product_id=line.product_id,
                        warehouse_id=line.warehouse_id,
                        quantity=Decimal(line.base_quantity),
                        amount=Decimal(line.cost_amount),
                        batch_no=line.batch_no,
                        serial_numbers=tuple(
                            json.loads(line.serial_numbers) if line.serial_numbers else []
                        ),
                    )
                    for line in lines
                ),
                occurred_at=datetime.combine(sales_return.business_date, now.time()),
                operator_id=self.user_id,
            )
        )
        for line in lines:
            source_lines[line.delivery_line_id].returned_quantity = quantize(
                Decimal(source_lines[line.delivery_line_id].returned_quantity)
                + Decimal(line.base_quantity),
                QTY,
            )
        sales_return.status = "approved"
        sales_return.posting_version = version
        sales_return.approved_by_id = self.user_id
        sales_return.approved_at = now
        await self.db.flush()
        await self.receivables.recognize_return(sales_return, delivery)
        return await self.detail(return_id)

    async def unapprove(self, return_id: int):
        """反审核退货单并冲销回库和红字应收。"""

        sales_return = await self._lock(return_id)
        if sales_return.status != "approved":
            raise CustomException("只有已审核销售退货单可以反审核")
        lines = await self._lines(return_id, lock=True)
        await self.receivables.reverse_return(sales_return)
        await StockPostingEngine(self.db).reverse(
            source_type="sales_return",
            source_id=sales_return.id,
            posting_version=sales_return.posting_version,
            source_no=sales_return.return_no,
            operator_id=self.user_id,
        )
        source_lines = {
            item.id: item
            for item in (
                await self.db.scalars(
                    select(models.ErpSalesDeliveryLine)
                    .where(
                        models.ErpSalesDeliveryLine.id.in_(
                            [line.delivery_line_id for line in lines]
                        )
                    )
                    .with_for_update()
                )
            ).all()
        }
        for line in lines:
            source = source_lines[line.delivery_line_id]
            source.returned_quantity = quantize(
                Decimal(source.returned_quantity) - Decimal(line.base_quantity), QTY
            )
        sales_return.status = "draft"
        sales_return.approved_by_id = None
        sales_return.approved_at = None
        await self.db.flush()
        return await self.detail(return_id)

    async def detail(self, return_id: int):
        """返回销售退货单和退货商品明细。"""

        doc = await self.db.get(models.ErpSalesReturn, return_id)
        if doc is None or doc.is_delete:
            raise CustomException("销售退货单不存在")
        await self.db.refresh(doc)
        result = {key: getattr(doc, key) for key in doc.get_column_attrs()}
        result["lines"] = []
        lines = list(await self._lines(return_id))
        products = await self.product_views(line.product_id for line in lines)
        for line in lines:
            item = {key: getattr(line, key) for key in line.get_column_attrs()}
            item["serial_numbers"] = json.loads(line.serial_numbers) if line.serial_numbers else []
            item["product"] = products.get(line.product_id)
            result["lines"].append(item)
        return jsonable_encoder(result)

    async def delete(self, ids: list[int]):
        """批量删除草稿销售退货单。"""

        docs = list(
            (await self.db.scalars(select(models.ErpSalesReturn).where(models.ErpSalesReturn.id.in_(ids)))).all()
        )
        if len(docs) != len(set(ids)) or any(item.status != "draft" for item in docs):
            raise CustomException("只能删除存在的草稿销售退货单")
        await self.db.execute(
            delete(models.ErpSalesReturnLine).where(models.ErpSalesReturnLine.return_id.in_(ids))
        )
        await self.db.execute(delete(models.ErpSalesReturn).where(models.ErpSalesReturn.id.in_(ids)))

    async def _lock(self, return_id: int):
        """锁定销售退货单表头。"""

        doc = await self.db.scalar(
            select(models.ErpSalesReturn)
            .where(
                models.ErpSalesReturn.id == return_id,
                models.ErpSalesReturn.is_delete == false(),
            )
            .with_for_update()
        )
        if doc is None:
            raise CustomException("销售退货单不存在")
        return doc

    async def _lines(self, return_id: int, lock: bool = False):
        """读取销售退货明细并可选加锁。"""

        sql = select(models.ErpSalesReturnLine).where(
            models.ErpSalesReturnLine.return_id == return_id
        ).order_by(models.ErpSalesReturnLine.line_no)
        if lock:
            sql = sql.with_for_update()
        return list((await self.db.scalars(sql)).all())
