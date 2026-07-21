"""成本流水冲销规则。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from core.exception import CustomException

from ... import models
from apps.erp.common import MONEY, QTY, quantize
from .types import CostPostingResult, CostType


class CostReversalMixin:
    """处理库存成本流水和价值调整流水的倒序冲销。"""

    async def reverse_stock_movement(
        self,
        stock_movement_id: int,
        source_type: str,
        source_id: int,
        source_no: str,
        posting_version: int,
        occurred_at: datetime,
        operator_id: int | None = None,
    ) -> CostPostingResult:
        """为指定库存流水生成一条方向相反的成本流水。"""

        original = await self.db.scalar(
            select(models.ErpInventoryCostLedger).where(
                models.ErpInventoryCostLedger.stock_movement_id == stock_movement_id
            )
        )
        if original is None:
            raise CustomException("找不到库存流水对应的成本流水")
        return await self._reverse_ledger(
            original,
            idempotency_key=f"COST:REVERSE:{original.id}",
            cost_no=f"{source_no[:55]}-CR{original.id}",
            source_type=source_type,
            source_id=source_id,
            source_no=source_no,
            posting_version=posting_version,
            occurred_at=occurred_at,
            operator_id=operator_id,
            attach_later=True,
        )

    async def reverse_value_change(
        self,
        original_cost_ledger_id: int,
        source_type: str,
        source_id: int,
        source_no: str,
        posting_version: int,
        occurred_at: datetime | None = None,
        operator_id: int | None = None,
        remark: str | None = None,
    ) -> CostPostingResult:
        """冲销一条成本调整或重新计价流水并同步成本镜像。"""

        original = await self.db.get(models.ErpInventoryCostLedger, original_cost_ledger_id)
        if original is None or original.cost_type not in {
            CostType.ADJUSTMENT.value,
            CostType.REVALUATION.value,
        }:
            raise CustomException("只能直接冲销成本调整或重新计价流水")
        inventory_balance = await self._lock_inventory_balance(
            original.warehouse_id, original.product_id
        )
        result = await self._reverse_ledger(
            original,
            idempotency_key=f"COST:REVERSE:{original.id}",
            cost_no=f"{source_no[:55]}-CR{original.id}",
            source_type=source_type,
            source_id=source_id,
            source_no=source_no,
            posting_version=posting_version,
            occurred_at=occurred_at or datetime.now(),
            operator_id=operator_id,
            attach_later=False,
            remark=remark,
        )
        await self._mirror_inventory_balance(result.balance, inventory_balance)
        return result

    async def _reverse_ledger(
        self,
        original: models.ErpInventoryCostLedger,
        *,
        idempotency_key: str,
        cost_no: str,
        source_type: str,
        source_id: int,
        source_no: str,
        posting_version: int,
        occurred_at: datetime,
        operator_id: int | None,
        attach_later: bool,
        remark: str | None = None,
    ) -> CostPostingResult:
        """校验成本链顺序并精确恢复原流水过账前余额。"""

        existing = await self._existing_result(idempotency_key)
        if existing:
            return existing
        await self._ensure_no_later_unreversed(original)
        balance = await self._lock_balance(original.warehouse_id, original.product_id)
        if (
            quantize(Decimal(balance.quantity), QTY)
            != quantize(Decimal(original.balance_quantity_after), QTY)
            or quantize(Decimal(balance.inventory_value), MONEY)
            != quantize(Decimal(original.balance_value_after), MONEY)
        ):
            raise CustomException("成本余额与原成本流水不一致，不能冲销")
        balance.quantity = original.balance_quantity_before
        balance.inventory_value = original.balance_value_before
        balance.average_cost = original.average_cost_before
        balance.needs_revaluation = bool(original.provisional)
        balance.last_cost_at = occurred_at
        ledger = models.ErpInventoryCostLedger(
            cost_no=cost_no[:80],
            idempotency_key=idempotency_key,
            cost_type=CostType.REVERSAL.value,
            source_type=source_type,
            source_id=source_id,
            source_no=source_no,
            source_line_id=original.source_line_id,
            cost_role=f"reverse_{original.cost_role}"[:30],
            posting_version=posting_version,
            stock_movement_id=None,
            reversal_of_id=original.id,
            warehouse_id=original.warehouse_id,
            product_id=original.product_id,
            quantity=-Decimal(original.quantity),
            amount=-Decimal(original.amount),
            balance_quantity_before=original.balance_quantity_after,
            balance_quantity_after=original.balance_quantity_before,
            balance_value_before=original.balance_value_after,
            balance_value_after=original.balance_value_before,
            average_cost_before=original.average_cost_after,
            average_cost_after=original.average_cost_before,
            provisional=original.provisional,
            occurred_at=occurred_at,
            operator_id=operator_id,
            remark=remark or f"冲销成本流水 {original.cost_no}",
        )
        result = self._result(ledger, balance)
        if not attach_later:
            self.db.add(ledger)
            await self.db.flush()
            balance.last_cost_ledger_id = ledger.id
        return result

    async def _ensure_no_later_unreversed(self, original):
        """确保原流水之后不存在尚未冲销的成本业务。"""

        later_entries = list(
            (
                await self.db.scalars(
                    select(models.ErpInventoryCostLedger)
                    .where(
                        models.ErpInventoryCostLedger.warehouse_id == original.warehouse_id,
                        models.ErpInventoryCostLedger.product_id == original.product_id,
                        models.ErpInventoryCostLedger.id > original.id,
                        models.ErpInventoryCostLedger.reversal_of_id.is_(None),
                    )
                    .order_by(models.ErpInventoryCostLedger.id)
                )
            ).all()
        )
        for later in later_entries:
            reversed_id = await self.db.scalar(
                select(models.ErpInventoryCostLedger.id).where(
                    models.ErpInventoryCostLedger.reversal_of_id == later.id
                )
            )
            if reversed_id is None:
                raise CustomException("存在未冲销的后续成本业务，请先按倒序冲销")
