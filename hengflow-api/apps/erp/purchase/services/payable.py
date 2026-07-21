"""供应商应付、退货红字、付款核销和不可变流水服务。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from apps.erp.common import MONEY, quantize
from core.exception import CustomException
from .. import models


class PayableService:
    """维护供应商应付余额、开放项目、付款核销和不可变流水。"""

    def __init__(self, db, user_id: int | None = None):
        """绑定当前事务与操作人。"""

        self.db = db
        self.user_id = user_id

    async def recognize_receipt(self, receipt):
        """采购收货审核时生成应付开放项目。"""

        payable = await self.db.scalar(select(models.ErpPayable).where(models.ErpPayable.receipt_id == receipt.id))
        if payable is None:
            payable = models.ErpPayable(
                payable_no=f"AP-{receipt.receipt_no}", supplier_id=receipt.supplier_id,
                receipt_id=receipt.id, receipt_no=receipt.receipt_no,
                business_date=receipt.business_date, due_date=receipt.due_date,
                original_amount=receipt.payable_amount, settled_amount=0, returned_amount=0,
                outstanding_amount=receipt.payable_amount,
                status="open" if Decimal(receipt.payable_amount) else "settled",
            )
            self.db.add(payable)
            await self.db.flush()
        elif payable.status == "voided" and not Decimal(payable.settled_amount) and not Decimal(payable.returned_amount):
            payable.original_amount = receipt.payable_amount
            payable.outstanding_amount = receipt.payable_amount
            payable.due_date = receipt.due_date
            payable.status = "open" if Decimal(receipt.payable_amount) else "settled"
        await self.post_entry(
            supplier_id=receipt.supplier_id, payable_id=payable.id,
            source_type="purchase_receipt", source_id=receipt.id, source_no=receipt.receipt_no,
            posting_version=receipt.posting_version, entry_type="PURCHASE",
            amount=Decimal(receipt.payable_amount), occurred_at=receipt.approved_at or datetime.now(),
        )
        return payable

    async def reverse_receipt(self, receipt):
        """冲销未发生退货和付款的采购收货应付。"""

        payable = await self._lock_by_receipt(receipt.id)
        if Decimal(payable.settled_amount) or Decimal(payable.returned_amount):
            raise CustomException("该采购收货已发生退货或付款，不能反审核")
        await self.reverse_entry("purchase_receipt", receipt.id, receipt.posting_version)
        payable.outstanding_amount = 0
        payable.status = "voided"

    async def recognize_return(self, purchase_return):
        """采购退货审核时减少原收货应付。"""

        payable = await self._lock_by_receipt(purchase_return.receipt_id)
        amount = quantize(Decimal(purchase_return.payable_amount), MONEY)
        if amount > Decimal(payable.outstanding_amount):
            raise CustomException("退货金额超过原收货未付金额，请先撤销相关付款")
        payable.returned_amount = quantize(Decimal(payable.returned_amount) + amount, MONEY)
        payable.outstanding_amount = quantize(Decimal(payable.outstanding_amount) - amount, MONEY)
        self._refresh_status(payable)
        await self.post_entry(
            supplier_id=purchase_return.supplier_id, payable_id=payable.id,
            source_type="purchase_return", source_id=purchase_return.id,
            source_no=purchase_return.return_no, posting_version=purchase_return.posting_version,
            entry_type="RETURN", amount=-amount,
            occurred_at=purchase_return.approved_at or datetime.now(),
        )

    async def reverse_return(self, purchase_return):
        """反审核采购退货时恢复原应付项目。"""

        payable = await self._lock_by_receipt(purchase_return.receipt_id)
        amount = quantize(Decimal(purchase_return.payable_amount), MONEY)
        if Decimal(payable.returned_amount) < amount:
            raise CustomException("应付项目退货金额不足，不能反审核")
        payable.returned_amount = quantize(Decimal(payable.returned_amount) - amount, MONEY)
        payable.outstanding_amount = quantize(Decimal(payable.outstanding_amount) + amount, MONEY)
        self._refresh_status(payable)
        await self.reverse_entry("purchase_return", purchase_return.id, purchase_return.posting_version)

    async def approve_payment(self, payment, requested):
        """审核付款并按指定项目或到期顺序核销应付。"""

        allocations = await self._resolve_allocations(payment, requested)
        allocated = Decimal(0)
        for payable, amount in allocations:
            amount = quantize(amount, MONEY)
            payable.settled_amount = quantize(Decimal(payable.settled_amount) + amount, MONEY)
            payable.outstanding_amount = quantize(Decimal(payable.outstanding_amount) - amount, MONEY)
            self._refresh_status(payable)
            self.db.add(models.ErpPurchasePaymentAllocation(payment_id=payment.id, payable_id=payable.id, amount=amount))
            allocated += amount
        if allocated > Decimal(payment.amount):
            raise CustomException("核销金额不能大于付款金额")
        await self.post_entry(
            supplier_id=payment.supplier_id, payable_id=None,
            source_type="purchase_payment", source_id=payment.id, source_no=payment.payment_no,
            posting_version=payment.posting_version, entry_type="PAYMENT",
            amount=-Decimal(payment.amount), occurred_at=payment.approved_at or datetime.now(),
        )

    async def unapprove_payment(self, payment):
        """反审核付款并撤销全部应付核销。"""

        allocations = list((await self.db.scalars(select(models.ErpPurchasePaymentAllocation).where(models.ErpPurchasePaymentAllocation.payment_id == payment.id).with_for_update())).all())
        for allocation in allocations:
            payable = await self.db.scalar(select(models.ErpPayable).where(models.ErpPayable.id == allocation.payable_id).with_for_update())
            payable.settled_amount = quantize(Decimal(payable.settled_amount) - Decimal(allocation.amount), MONEY)
            payable.outstanding_amount = quantize(Decimal(payable.outstanding_amount) + Decimal(allocation.amount), MONEY)
            self._refresh_status(payable)
            await self.db.delete(allocation)
        await self.reverse_entry("purchase_payment", payment.id, payment.posting_version)

    async def post_entry(self, *, supplier_id, payable_id, source_type, source_id, source_no, posting_version, entry_type, amount, occurred_at):
        """以幂等方式更新供应商余额并写入不可变应付流水。"""

        key = f"AP:{source_type}:{source_id}:V{posting_version}"
        existing = await self.db.scalar(select(models.ErpPayableLedger).where(models.ErpPayableLedger.idempotency_key == key))
        if existing:
            return existing
        balance = await self._lock_balance(supplier_id)
        before = quantize(Decimal(balance.amount), MONEY)
        after = quantize(before + Decimal(amount), MONEY)
        balance.amount = after
        balance.last_occurred_at = occurred_at
        ledger = models.ErpPayableLedger(
            entry_no=f"{source_no}-{entry_type}-V{posting_version}"[:80], idempotency_key=key,
            entry_type=entry_type, supplier_id=supplier_id, payable_id=payable_id,
            source_type=source_type, source_id=source_id, source_no=source_no,
            posting_version=posting_version, reversal_of_id=None,
            amount=quantize(Decimal(amount), MONEY), balance_before=before, balance_after=after,
            occurred_at=occurred_at, operator_id=self.user_id,
        )
        self.db.add(ledger)
        await self.db.flush()
        balance.last_entry_id = ledger.id
        return ledger

    async def reverse_entry(self, source_type, source_id, posting_version):
        """为指定应付业务生成方向相反的冲销流水。"""

        original = await self.db.scalar(select(models.ErpPayableLedger).where(
            models.ErpPayableLedger.source_type == source_type,
            models.ErpPayableLedger.source_id == source_id,
            models.ErpPayableLedger.posting_version == posting_version,
            models.ErpPayableLedger.reversal_of_id.is_(None),
        ))
        if original is None:
            raise CustomException("找不到需要冲销的应付流水")
        key = f"AP:REVERSE:{original.id}"
        existing = await self.db.scalar(select(models.ErpPayableLedger).where(models.ErpPayableLedger.idempotency_key == key))
        if existing:
            return existing
        balance = await self._lock_balance(original.supplier_id)
        before = quantize(Decimal(balance.amount), MONEY)
        after = quantize(before - Decimal(original.amount), MONEY)
        balance.amount = after
        reversal = models.ErpPayableLedger(
            entry_no=f"{original.source_no}-AP-R{original.id}"[:80], idempotency_key=key,
            entry_type="REVERSAL", supplier_id=original.supplier_id, payable_id=original.payable_id,
            source_type=source_type, source_id=source_id, source_no=original.source_no,
            posting_version=posting_version, reversal_of_id=original.id,
            amount=-Decimal(original.amount), balance_before=before, balance_after=after,
            occurred_at=datetime.now(), operator_id=self.user_id,
        )
        self.db.add(reversal)
        await self.db.flush()
        balance.last_entry_id = reversal.id
        balance.last_occurred_at = reversal.occurred_at
        return reversal

    async def _resolve_allocations(self, payment, requested):
        """校验指定核销，未指定时按到期日自动核销。"""

        remaining, result = quantize(Decimal(payment.amount), MONEY), []
        if requested:
            if len({x.payable_id for x in requested}) != len(requested):
                raise CustomException("同一应付项目不能重复核销")
            for item in requested:
                payable = await self.db.scalar(select(models.ErpPayable).where(
                    models.ErpPayable.id == item.payable_id,
                    models.ErpPayable.supplier_id == payment.supplier_id,
                    models.ErpPayable.status.in_(("open", "partial")),
                ).with_for_update())
                if payable is None or Decimal(item.amount) > Decimal(payable.outstanding_amount):
                    raise CustomException("付款核销项目无效或金额超过未付金额")
                result.append((payable, Decimal(item.amount)))
                remaining -= Decimal(item.amount)
            if remaining < 0:
                raise CustomException("核销金额不能大于付款金额")
            return result
        payables = list((await self.db.scalars(select(models.ErpPayable).where(
            models.ErpPayable.supplier_id == payment.supplier_id,
            models.ErpPayable.outstanding_amount > 0,
            models.ErpPayable.is_delete == False,
        ).order_by(models.ErpPayable.due_date, models.ErpPayable.business_date).with_for_update())).all())
        for payable in payables:
            if remaining <= 0:
                break
            amount = min(remaining, Decimal(payable.outstanding_amount))
            result.append((payable, amount))
            remaining -= amount
        return result

    async def _lock_balance(self, supplier_id):
        """创建并锁定供应商应付余额。"""

        await self.db.execute(mysql_insert(models.ErpSupplierPayableBalance).values(supplier_id=supplier_id, amount=0).on_duplicate_key_update(id=models.ErpSupplierPayableBalance.id))
        return await self.db.scalar(select(models.ErpSupplierPayableBalance).where(models.ErpSupplierPayableBalance.supplier_id == supplier_id).with_for_update())

    async def _lock_by_receipt(self, receipt_id):
        """锁定采购收货对应应付项目。"""

        payable = await self.db.scalar(select(models.ErpPayable).where(models.ErpPayable.receipt_id == receipt_id).with_for_update())
        if payable is None:
            raise CustomException("采购收货对应的应付项目不存在")
        return payable

    @staticmethod
    def _refresh_status(payable):
        """按未付金额刷新应付项目状态。"""

        if Decimal(payable.outstanding_amount) <= 0:
            payable.status = "settled"
        elif Decimal(payable.settled_amount) or Decimal(payable.returned_amount):
            payable.status = "partial"
        else:
            payable.status = "open"
