"""销售应收、退货红字和收款核销服务。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import false, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from apps.erp.common import MONEY, quantize
from core.exception import CustomException

from .. import models


class ReceivableService:
    """维护客户应收余额、开放项目、收款核销和不可变流水。"""

    def __init__(self, db, user_id: int | None = None):
        """绑定当前业务事务和操作人。"""

        self.db = db
        self.user_id = user_id

    async def recognize_delivery(self, delivery):
        """销售出库审核时生成应收开放项目和应收增加流水。"""

        receivable = await self.db.scalar(
            select(models.ErpReceivable).where(models.ErpReceivable.delivery_id == delivery.id)
        )
        if receivable is None:
            receivable = models.ErpReceivable(
                receivable_no=f"AR-{delivery.delivery_no}",
                customer_id=delivery.customer_id,
                delivery_id=delivery.id,
                delivery_no=delivery.delivery_no,
                business_date=delivery.business_date,
                due_date=delivery.due_date,
                original_amount=delivery.payable_amount,
                settled_amount=0,
                returned_amount=0,
                outstanding_amount=delivery.payable_amount,
                status="open" if delivery.payable_amount else "settled",
            )
            self.db.add(receivable)
            await self.db.flush()
        await self.post_entry(
            customer_id=delivery.customer_id,
            receivable_id=receivable.id,
            source_type="sales_delivery",
            source_id=delivery.id,
            source_no=delivery.delivery_no,
            posting_version=delivery.posting_version,
            entry_type="SALE",
            amount=Decimal(delivery.payable_amount),
            occurred_at=delivery.approved_at or datetime.now(),
        )
        return receivable

    async def reverse_delivery(self, delivery):
        """反审核销售出库时冲销未发生退货和收款的应收项目。"""

        receivable = await self._lock_receivable_by_delivery(delivery.id)
        if Decimal(receivable.settled_amount) or Decimal(receivable.returned_amount):
            raise CustomException("该销售出库已发生退货或收款，不能反审核")
        await self.reverse_entry("sales_delivery", delivery.id, delivery.posting_version)
        receivable.outstanding_amount = 0
        receivable.status = "voided"

    async def recognize_return(self, sales_return, delivery):
        """销售退货审核时减少客户应收并更新原应收项目。"""

        receivable = await self._lock_receivable_by_delivery(delivery.id)
        amount = quantize(Decimal(sales_return.payable_amount), MONEY)
        receivable.returned_amount = quantize(Decimal(receivable.returned_amount) + amount, MONEY)
        receivable.outstanding_amount = max(
            Decimal("0"),
            quantize(
                Decimal(receivable.original_amount)
                - Decimal(receivable.settled_amount)
                - Decimal(receivable.returned_amount),
                MONEY,
            ),
        )
        self._refresh_status(receivable)
        await self.post_entry(
            customer_id=sales_return.customer_id,
            receivable_id=receivable.id,
            source_type="sales_return",
            source_id=sales_return.id,
            source_no=sales_return.return_no,
            posting_version=sales_return.posting_version,
            entry_type="RETURN",
            amount=-amount,
            occurred_at=sales_return.approved_at or datetime.now(),
        )

    async def reverse_return(self, sales_return):
        """反审核销售退货时恢复原应收项目并冲销红字流水。"""

        delivery = await self.db.get(models.ErpSalesDelivery, sales_return.delivery_id)
        receivable = await self._lock_receivable_by_delivery(delivery.id)
        amount = quantize(Decimal(sales_return.payable_amount), MONEY)
        if Decimal(receivable.returned_amount) < amount:
            raise CustomException("应收项目退货金额不足，不能反审核")
        receivable.returned_amount = quantize(Decimal(receivable.returned_amount) - amount, MONEY)
        receivable.outstanding_amount = max(
            Decimal("0"),
            quantize(
                Decimal(receivable.original_amount)
                - Decimal(receivable.settled_amount)
                - Decimal(receivable.returned_amount),
                MONEY,
            ),
        )
        self._refresh_status(receivable)
        await self.reverse_entry("sales_return", sales_return.id, sales_return.posting_version)

    async def approve_receipt(self, receipt, requested_allocations):
        """审核收款单，按指定明细或到期顺序核销客户应收。"""

        allocations = await self._resolve_allocations(receipt, requested_allocations)
        allocated = Decimal("0")
        for receivable, amount in allocations:
            amount = quantize(amount, MONEY)
            receivable.settled_amount = quantize(Decimal(receivable.settled_amount) + amount, MONEY)
            receivable.outstanding_amount = quantize(
                Decimal(receivable.outstanding_amount) - amount, MONEY
            )
            self._refresh_status(receivable)
            self.db.add(
                models.ErpSalesReceiptAllocation(
                    receipt_id=receipt.id,
                    receivable_id=receivable.id,
                    amount=amount,
                )
            )
            allocated += amount
        if allocated > Decimal(receipt.amount):
            raise CustomException("核销金额不能大于收款金额")
        await self.post_entry(
            customer_id=receipt.customer_id,
            receivable_id=None,
            source_type="sales_receipt",
            source_id=receipt.id,
            source_no=receipt.receipt_no,
            posting_version=receipt.posting_version,
            entry_type="RECEIPT",
            amount=-Decimal(receipt.amount),
            occurred_at=receipt.approved_at or datetime.now(),
        )

    async def unapprove_receipt(self, receipt):
        """反审核收款单，撤销核销金额并冲销应收流水。"""

        allocations = list(
            (
                await self.db.scalars(
                    select(models.ErpSalesReceiptAllocation)
                    .where(models.ErpSalesReceiptAllocation.receipt_id == receipt.id)
                    .with_for_update()
                )
            ).all()
        )
        for allocation in allocations:
            receivable = await self.db.scalar(
                select(models.ErpReceivable)
                .where(models.ErpReceivable.id == allocation.receivable_id)
                .with_for_update()
            )
            receivable.settled_amount = quantize(
                Decimal(receivable.settled_amount) - Decimal(allocation.amount), MONEY
            )
            receivable.outstanding_amount = quantize(
                Decimal(receivable.outstanding_amount) + Decimal(allocation.amount), MONEY
            )
            self._refresh_status(receivable)
            await self.db.delete(allocation)
        await self.reverse_entry("sales_receipt", receipt.id, receipt.posting_version)

    async def post_entry(
        self,
        *,
        customer_id: int,
        receivable_id: int | None,
        source_type: str,
        source_id: int,
        source_no: str,
        posting_version: int,
        entry_type: str,
        amount: Decimal,
        occurred_at: datetime,
    ):
        """以幂等方式更新客户余额并写入不可变应收流水。"""

        key = f"AR:{source_type}:{source_id}:V{posting_version}"
        existing = await self.db.scalar(
            select(models.ErpReceivableLedger).where(
                models.ErpReceivableLedger.idempotency_key == key
            )
        )
        if existing:
            return existing
        balance = await self._lock_balance(customer_id)
        before = quantize(Decimal(balance.amount), MONEY)
        after = quantize(before + Decimal(amount), MONEY)
        balance.amount = after
        balance.last_occurred_at = occurred_at
        ledger = models.ErpReceivableLedger(
            entry_no=f"{source_no}-{entry_type}-V{posting_version}"[:80],
            idempotency_key=key,
            entry_type=entry_type,
            customer_id=customer_id,
            receivable_id=receivable_id,
            source_type=source_type,
            source_id=source_id,
            source_no=source_no,
            posting_version=posting_version,
            reversal_of_id=None,
            amount=quantize(Decimal(amount), MONEY),
            balance_before=before,
            balance_after=after,
            occurred_at=occurred_at,
            operator_id=self.user_id,
        )
        self.db.add(ledger)
        await self.db.flush()
        balance.last_entry_id = ledger.id
        return ledger

    async def reverse_entry(self, source_type: str, source_id: int, posting_version: int):
        """为指定业务应收流水生成方向相反的幂等冲销流水。"""

        original = await self.db.scalar(
            select(models.ErpReceivableLedger).where(
                models.ErpReceivableLedger.source_type == source_type,
                models.ErpReceivableLedger.source_id == source_id,
                models.ErpReceivableLedger.posting_version == posting_version,
                models.ErpReceivableLedger.reversal_of_id.is_(None),
            )
        )
        if original is None:
            raise CustomException("找不到需要冲销的应收流水")
        key = f"AR:REVERSE:{original.id}"
        existing = await self.db.scalar(
            select(models.ErpReceivableLedger).where(
                models.ErpReceivableLedger.idempotency_key == key
            )
        )
        if existing:
            return existing
        balance = await self._lock_balance(original.customer_id)
        before = quantize(Decimal(balance.amount), MONEY)
        after = quantize(before - Decimal(original.amount), MONEY)
        balance.amount = after
        balance.last_occurred_at = datetime.now()
        reversal = models.ErpReceivableLedger(
            entry_no=f"{original.source_no}-AR-R{original.id}"[:80],
            idempotency_key=key,
            entry_type="REVERSAL",
            customer_id=original.customer_id,
            receivable_id=original.receivable_id,
            source_type=source_type,
            source_id=source_id,
            source_no=original.source_no,
            posting_version=posting_version,
            reversal_of_id=original.id,
            amount=-Decimal(original.amount),
            balance_before=before,
            balance_after=after,
            occurred_at=datetime.now(),
            operator_id=self.user_id,
        )
        self.db.add(reversal)
        await self.db.flush()
        balance.last_entry_id = reversal.id
        return reversal

    async def _resolve_allocations(self, receipt, requested):
        """校验指定核销明细，未指定时按到期日自动核销。"""

        remaining = quantize(Decimal(receipt.amount), MONEY)
        result = []
        if requested:
            if len({item.receivable_id for item in requested}) != len(requested):
                raise CustomException("同一应收项目不能重复核销")
            for item in requested:
                receivable = await self.db.scalar(
                    select(models.ErpReceivable)
                    .where(
                        models.ErpReceivable.id == item.receivable_id,
                        models.ErpReceivable.customer_id == receipt.customer_id,
                        models.ErpReceivable.status.in_(("open", "partial")),
                    )
                    .with_for_update()
                )
                if receivable is None or Decimal(item.amount) > Decimal(receivable.outstanding_amount):
                    raise CustomException("收款核销明细无效或金额超过未收金额")
                result.append((receivable, Decimal(item.amount)))
                remaining -= Decimal(item.amount)
            if remaining < 0:
                raise CustomException("核销金额不能大于收款金额")
            return result
        receivables = list(
            (
                await self.db.scalars(
                    select(models.ErpReceivable)
                    .where(
                        models.ErpReceivable.customer_id == receipt.customer_id,
                        models.ErpReceivable.outstanding_amount > 0,
                        models.ErpReceivable.is_delete == false(),
                    )
                    .order_by(models.ErpReceivable.due_date, models.ErpReceivable.business_date)
                    .with_for_update()
                )
            ).all()
        )
        for receivable in receivables:
            if remaining <= 0:
                break
            amount = min(remaining, Decimal(receivable.outstanding_amount))
            result.append((receivable, amount))
            remaining -= amount
        return result

    async def _lock_balance(self, customer_id: int):
        """创建并行锁定客户应收余额。"""

        await self.db.execute(
            mysql_insert(models.ErpCustomerReceivableBalance)
            .values(customer_id=customer_id, amount=0)
            .on_duplicate_key_update(id=models.ErpCustomerReceivableBalance.id)
        )
        return await self.db.scalar(
            select(models.ErpCustomerReceivableBalance)
            .where(models.ErpCustomerReceivableBalance.customer_id == customer_id)
            .with_for_update()
        )

    async def _lock_receivable_by_delivery(self, delivery_id: int):
        """锁定销售出库对应的应收开放项目。"""

        receivable = await self.db.scalar(
            select(models.ErpReceivable)
            .where(models.ErpReceivable.delivery_id == delivery_id)
            .with_for_update()
        )
        if receivable is None:
            raise CustomException("销售出库对应的应收项目不存在")
        return receivable

    @staticmethod
    def _refresh_status(receivable):
        """根据未收金额刷新应收开放项目状态。"""

        if Decimal(receivable.outstanding_amount) <= 0:
            receivable.status = "settled"
        elif Decimal(receivable.settled_amount) or Decimal(receivable.returned_amount):
            receivable.status = "partial"
        else:
            receivable.status = "open"
