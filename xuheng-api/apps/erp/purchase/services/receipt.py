"""采购收货、订单履约、库存和应付联动服务。"""

import json
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, false, select

from apps.erp.inventory.services.stock import MovementType, PostingRequest, StockMovement, StockPostingEngine
from apps.erp.common.settlement import calculate_document_settlement
from apps.erp.master import models as master_models
from core.exception import CustomException
from apps.erp.finance.services.period import AccountingPeriodService
from .. import models, schemas
from .common import PurchaseServiceSupport
from .payable import PayableService


class PurchaseReceiptService(PurchaseServiceSupport):
    """管理采购分批收货并同步库存、成本、订单进度和应付。"""

    async def save(self, data: schemas.PurchaseReceiptInput, receipt_id: int | None = None):
        """新增或修改采购收货草稿。"""

        await AccountingPeriodService(self.db, self.user_id).ensure_open(data.business_date, "新增或修改采购收货单")

        lines = await self.prepare_lines(data, tracking=True)
        await self._validate_order(data, lines)
        supplier = await self.active(master_models.ErpSupplier, data.supplier_id, "供应商")
        if receipt_id:
            receipt = await self._lock(receipt_id)
            if receipt.status != "draft":
                raise CustomException("只有草稿采购收货单可以修改")
            await self.db.execute(delete(models.ErpPurchaseReceiptLine).where(models.ErpPurchaseReceiptLine.receipt_id == receipt_id))
        else:
            number = data.receipt_no or await self.next_no("purchase_receipt", "PR", data.business_date)
            if await self.db.scalar(select(models.ErpPurchaseReceipt.id).where(models.ErpPurchaseReceipt.receipt_no == number)):
                raise CustomException("采购收货单号已存在")
            receipt = models.ErpPurchaseReceipt(receipt_no=number, created_by_id=self.user_id)
            self.db.add(receipt)
        for field in (
            "business_date", "supplier_id", "warehouse_id", "employee_id", "order_id",
            "settlement_method_id", "fund_account_id", "remark",
        ):
            setattr(receipt, field, getattr(data, field))
        receipt.due_date = data.due_date or data.business_date + timedelta(days=supplier.payment_days or 0)
        totals = self.totals(lines)
        settlement = calculate_document_settlement(
            totals["payable_amount"], data.settlement_discount_rate,
            data.rounding_amount, data.current_payment_amount,
        )
        totals["payable_amount"] = settlement["settlement_amount"]
        for field, value in {**totals, **settlement}.items():
            setattr(receipt, field, value)
        await self.db.flush()
        for line in lines:
            line.pop("receipt_line_id", None)
            self.db.add(models.ErpPurchaseReceiptLine(receipt_id=receipt.id, returned_quantity=0, **line))
        await self.db.flush()
        return await self.detail(models.ErpPurchaseReceipt, models.ErpPurchaseReceiptLine, "receipt_id", receipt.id)

    async def approve(self, receipt_id: int):
        """审核收货并在同一事务内完成库存、订单和应付过账。"""

        receipt = await self._lock(receipt_id)
        if receipt.status != "draft":
            raise CustomException("只有草稿采购收货单可以审核")
        lines = await self._lines(receipt.id, True)
        await self._validate_remaining(receipt, lines)
        version, now = receipt.posting_version + 1, datetime.now()
        await StockPostingEngine(self.db).post(PostingRequest(
            source_type="purchase_receipt", source_id=receipt.id, source_no=receipt.receipt_no,
            posting_version=version, occurred_at=datetime.combine(receipt.business_date, now.time()), operator_id=self.user_id,
            movements=tuple(StockMovement(
                movement_type=MovementType.PURCHASE_IN, business_line_id=line.id,
                movement_role="purchase_receipt", product_id=line.product_id,
                warehouse_id=line.warehouse_id, quantity=Decimal(line.base_quantity),
                amount=Decimal(line.amount), batch_no=line.batch_no,
                production_date=line.production_date, expiry_date=line.expiry_date,
                serial_numbers=tuple(json.loads(line.serial_numbers) if line.serial_numbers else []),
            ) for line in lines),
        ))
        receipt.status = "approved"
        receipt.posting_version = version
        receipt.approved_by_id = self.user_id
        receipt.approved_at = now
        await self._apply_order(receipt, lines, Decimal(1))
        await self.db.flush()
        payable = await PayableService(self.db, self.user_id).recognize_receipt(receipt)
        if Decimal(receipt.current_payment_amount) > 0:
            if not receipt.fund_account_id:
                raise CustomException("填写本次付款后必须选择付款账户")
            from .payment import PurchasePaymentService

            payment_service = PurchasePaymentService(self.db, self.user_id)
            auto_payment = await payment_service.save(
                schemas.PurchasePaymentInput(
                    payment_date=receipt.business_date,
                    supplier_id=receipt.supplier_id,
                    settlement_method_id=receipt.settlement_method_id,
                    fund_account_id=receipt.fund_account_id,
                    amount=receipt.current_payment_amount,
                    allocations=[
                        schemas.PaymentAllocationInput(
                            payable_id=payable.id, amount=receipt.current_payment_amount
                        )
                    ],
                    remark=f"由采购入库 {receipt.receipt_no} 审核自动生成",
                )
            )
            await payment_service.approve(auto_payment["id"])
            receipt.linked_payment_id = auto_payment["id"]
            await self.db.flush()
        return await self.detail(models.ErpPurchaseReceipt, models.ErpPurchaseReceiptLine, "receipt_id", receipt.id)

    async def unapprove(self, receipt_id: int):
        """反审核无下游退货或付款的采购收货单。"""

        receipt = await self._lock(receipt_id)
        if receipt.status != "approved":
            raise CustomException("只有已审核采购收货单可以反审核")
        lines = await self._lines(receipt.id, True)
        if any(Decimal(line.returned_quantity) for line in lines):
            raise CustomException("采购收货已发生退货，不能反审核")
        if receipt.linked_payment_id:
            from .payment import PurchasePaymentService

            payment_service = PurchasePaymentService(self.db, self.user_id)
            linked_payment = await self.db.get(models.ErpPurchasePayment, receipt.linked_payment_id)
            if linked_payment and not linked_payment.is_delete:
                if linked_payment.status == "approved":
                    await payment_service.unapprove(linked_payment.id)
                await payment_service.delete([linked_payment.id])
            receipt.linked_payment_id = None
        await PayableService(self.db, self.user_id).reverse_receipt(receipt)
        await StockPostingEngine(self.db).reverse("purchase_receipt", receipt.id, receipt.posting_version, receipt.receipt_no, self.user_id)
        await self._apply_order(receipt, lines, Decimal(-1))
        receipt.status = "draft"
        receipt.approved_by_id = None
        receipt.approved_at = None
        await self.db.flush()
        return await self.detail(models.ErpPurchaseReceipt, models.ErpPurchaseReceiptLine, "receipt_id", receipt.id)

    async def delete(self, ids: list[int]):
        """删除采购收货草稿。"""

        docs = list((await self.db.scalars(select(models.ErpPurchaseReceipt).where(models.ErpPurchaseReceipt.id.in_(ids), models.ErpPurchaseReceipt.is_delete == false()))).all())
        if len(docs) != len(set(ids)) or any(x.status != "draft" for x in docs):
            raise CustomException("只能删除存在的草稿采购收货单")
        await self.db.execute(delete(models.ErpPurchaseReceiptLine).where(models.ErpPurchaseReceiptLine.receipt_id.in_(ids)))
        await self.db.execute(delete(models.ErpPurchaseReceipt).where(models.ErpPurchaseReceipt.id.in_(ids)))

    async def list(self, page, limit, status=None, keyword=None, supplier_id=None):
        """分页查询采购收货单。"""

        return await self.list_documents(models.ErpPurchaseReceipt, "receipt_no", page, limit, status, keyword, supplier_id)

    async def _validate_order(self, data, lines):
        """校验收货单和来源采购订单的一致性。"""

        if not data.order_id:
            return
        order = await self.db.get(models.ErpPurchaseOrder, data.order_id)
        if order is None or order.is_delete or order.status not in ("approved", "partial"):
            raise CustomException("采购订单不存在或不可继续收货")
        if order.supplier_id != data.supplier_id:
            raise CustomException("收货供应商与采购订单不一致")
        source = {x.id: x for x in (await self.db.scalars(select(models.ErpPurchaseOrderLine).where(models.ErpPurchaseOrderLine.order_id == order.id))).all()}
        for line in lines:
            original = source.get(line["order_line_id"])
            if original is None or original.product_id != line["product_id"]:
                raise CustomException("采购收货行与订单行不匹配")

    async def _validate_remaining(self, receipt, lines):
        """锁定来源订单行并防止并发超收。"""

        if not receipt.order_id:
            return
        requested = {}
        for line in lines:
            requested[line.order_line_id] = requested.get(line.order_line_id, Decimal(0)) + Decimal(line.base_quantity)
        sources = {
            source.id: source
            for source in (
                await self.db.scalars(
                    select(models.ErpPurchaseOrderLine)
                    .where(
                        models.ErpPurchaseOrderLine.id.in_(requested),
                        models.ErpPurchaseOrderLine.order_id == receipt.order_id,
                    )
                    .with_for_update()
                )
            ).all()
        }
        for line_id, quantity in requested.items():
            source = sources.get(line_id)
            if source is None or Decimal(source.received_quantity) + quantity > Decimal(source.base_quantity):
                raise CustomException("采购收货数量超过订单未收数量")

    async def _apply_order(self, receipt, lines, direction: Decimal):
        """增加或撤销订单行累计收货并刷新订单状态。"""

        if not receipt.order_id:
            return
        order = await self.db.scalar(select(models.ErpPurchaseOrder).where(models.ErpPurchaseOrder.id == receipt.order_id).with_for_update())
        order_lines = {x.id: x for x in (await self.db.scalars(select(models.ErpPurchaseOrderLine).where(models.ErpPurchaseOrderLine.order_id == order.id).with_for_update())).all()}
        for line in lines:
            source = order_lines[line.order_line_id]
            source.received_quantity = Decimal(source.received_quantity) + direction * Decimal(line.base_quantity)
        if direction < 0:
            order.status = "approved" if all(Decimal(x.received_quantity) == 0 for x in order_lines.values()) else "partial"
        else:
            order.status = "completed" if all(Decimal(x.received_quantity) >= Decimal(x.base_quantity) for x in order_lines.values()) else "partial"

    async def _lock(self, receipt_id):
        """锁定采购收货单。"""

        receipt = await self.db.scalar(select(models.ErpPurchaseReceipt).where(models.ErpPurchaseReceipt.id == receipt_id, models.ErpPurchaseReceipt.is_delete == false()).with_for_update())
        if receipt is None:
            raise CustomException("采购收货单不存在")
        return receipt

    async def _lines(self, receipt_id, lock=False):
        """读取采购收货明细。"""

        stmt = select(models.ErpPurchaseReceiptLine).where(models.ErpPurchaseReceiptLine.receipt_id == receipt_id).order_by(models.ErpPurchaseReceiptLine.line_no)
        if lock:
            stmt = stmt.with_for_update()
        return list((await self.db.scalars(stmt)).all())
