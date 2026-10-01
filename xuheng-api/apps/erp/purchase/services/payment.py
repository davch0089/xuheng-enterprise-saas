"""供应商付款单草稿、审核和反审核服务。"""

from datetime import datetime
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, false, select

from apps.erp.master import models as master_models
from core.exception import CustomException
from .. import models, schemas
from .common import PurchaseServiceSupport
from .payable import PayableService


class PurchasePaymentService(PurchaseServiceSupport):
    """管理供应商付款单并编排应付核销。"""

    async def save(self, data: schemas.PurchasePaymentInput, payment_id: int | None = None):
        """新增或修改付款草稿。"""

        from apps.erp.finance.services.period import AccountingPeriodService
        await AccountingPeriodService(self.db, self.user_id).ensure_open(data.payment_date, "新增或修改付款单")
        await self.active(master_models.ErpSupplier, data.supplier_id, "供应商")
        if data.settlement_method_id:
            await self.active(master_models.ErpSettlementMethod, data.settlement_method_id, "结算方式")
        if sum((Decimal(x.amount) for x in data.allocations), Decimal(0)) > Decimal(data.amount):
            raise CustomException("核销金额不能大于付款金额")
        if payment_id:
            payment = await self._lock(payment_id)
            if payment.status != "draft":
                raise CustomException("只有草稿付款单可以修改")
            await self.db.execute(delete(models.ErpPurchasePaymentAllocation).where(models.ErpPurchasePaymentAllocation.payment_id == payment_id))
        else:
            number = data.payment_no or await self.next_no("purchase_payment", "PP", data.payment_date)
            payment = models.ErpPurchasePayment(payment_no=number, created_by_id=self.user_id)
            self.db.add(payment)
        for field in ("payment_date", "supplier_id", "settlement_method_id", "fund_account_id", "amount", "remark"):
            setattr(payment, field, getattr(data, field))
        await self.db.flush()
        for item in data.allocations:
            self.db.add(models.ErpPurchasePaymentAllocation(payment_id=payment.id, payable_id=item.payable_id, amount=item.amount))
        await self.db.flush()
        return await self.detail(payment.id)

    async def approve(self, payment_id):
        """审核付款并正式核销供应商应付。"""

        payment = await self._lock(payment_id)
        if payment.status != "draft":
            raise CustomException("只有草稿付款单可以审核")
        if not payment.fund_account_id:
            raise CustomException("审核付款单前必须选择付款资金账户")
        allocations = list((await self.db.scalars(select(models.ErpPurchasePaymentAllocation).where(models.ErpPurchasePaymentAllocation.payment_id == payment.id))).all())
        requested = [schemas.PaymentAllocationInput(payable_id=x.payable_id, amount=x.amount) for x in allocations]
        if allocations:
            await self.db.execute(delete(models.ErpPurchasePaymentAllocation).where(models.ErpPurchasePaymentAllocation.payment_id == payment.id))
            await self.db.flush()
        payment.posting_version += 1
        payment.status = "approved"
        payment.approved_by_id = self.user_id
        payment.approved_at = datetime.now()
        await self.db.flush()
        await PayableService(self.db, self.user_id).approve_payment(payment, requested)
        from apps.erp.finance.services.fund import FundPostingEngine
        await FundPostingEngine(self.db, self.user_id).post(
            account_id=payment.fund_account_id, amount=-Decimal(payment.amount),
            source_type="purchase_payment", source_id=payment.id, source_no=payment.payment_no,
            posting_version=payment.posting_version, entry_type="SUPPLIER_PAYMENT",
            occurred_at=datetime.combine(payment.payment_date, payment.approved_at.time()),
        )
        return await self.detail(payment.id)

    async def unapprove(self, payment_id):
        """反审核付款并撤销应付核销。"""

        payment = await self._lock(payment_id)
        if payment.status != "approved":
            raise CustomException("只有已审核付款单可以反审核")
        from apps.erp.finance import models as finance_models
        linked = await self.db.scalar(select(finance_models.ErpSettlementDocument.id).where(
            finance_models.ErpSettlementDocument.source_payment_id == payment.id,
            finance_models.ErpSettlementDocument.status == "approved",
            finance_models.ErpSettlementDocument.is_delete == false(),
        ).limit(1))
        if linked is not None:
            raise CustomException("付款已被预付核销单使用，请先反审核核销单")
        from apps.erp.finance.services.fund import FundPostingEngine
        await FundPostingEngine(self.db, self.user_id).reverse("purchase_payment", payment.id, payment.posting_version)
        await PayableService(self.db, self.user_id).unapprove_payment(payment)
        payment.status = "draft"
        payment.approved_by_id = None
        payment.approved_at = None
        await self.db.flush()
        return await self.detail(payment.id)

    async def delete(self, ids):
        """删除供应商付款草稿。"""

        docs = list((await self.db.scalars(select(models.ErpPurchasePayment).where(models.ErpPurchasePayment.id.in_(ids), models.ErpPurchasePayment.is_delete == false()))).all())
        if len(docs) != len(set(ids)) or any(x.status != "draft" for x in docs):
            raise CustomException("只能删除存在的草稿付款单")
        from apps.erp.finance.services.period import AccountingPeriodService
        for item in docs:
            await AccountingPeriodService(self.db, self.user_id).ensure_open(item.payment_date, "删除付款单")
        await self.db.execute(delete(models.ErpPurchasePaymentAllocation).where(models.ErpPurchasePaymentAllocation.payment_id.in_(ids)))
        for item in docs:
            item.is_delete = True
        await self.db.flush()

    async def detail(self, payment_id):
        """返回付款表头和核销明细。"""

        payment = await self.db.get(models.ErpPurchasePayment, payment_id)
        if payment is None or payment.is_delete:
            raise CustomException("采购付款单不存在")
        await self.db.refresh(payment)
        allocations = list((await self.db.scalars(select(models.ErpPurchasePaymentAllocation).where(models.ErpPurchasePaymentAllocation.payment_id == payment_id))).all())
        payable_ids = [allocation.payable_id for allocation in allocations]
        payables = {
            payable.id: payable
            for payable in (
                await self.db.scalars(select(models.ErpPayable).where(models.ErpPayable.id.in_(payable_ids)))
            ).all()
        } if payable_ids else {}
        allocation_rows = []
        for allocation in allocations:
            row = {k: getattr(allocation, k) for k in allocation.get_column_attrs()}
            payable = payables.get(allocation.payable_id)
            if payable:
                row.update(
                    payable_no=payable.payable_no,
                    receipt_no=payable.receipt_no,
                    due_date=payable.due_date,
                    outstanding_amount=payable.outstanding_amount,
                )
            allocation_rows.append(row)
        return jsonable_encoder({**{k: getattr(payment, k) for k in payment.get_column_attrs()}, "allocations": allocation_rows})

    async def _lock(self, payment_id):
        """锁定采购付款单。"""

        payment = await self.db.scalar(select(models.ErpPurchasePayment).where(models.ErpPurchasePayment.id == payment_id, models.ErpPurchasePayment.is_delete == false()).with_for_update())
        if payment is None:
            raise CustomException("采购付款单不存在")
        return payment
