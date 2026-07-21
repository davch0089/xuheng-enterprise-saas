"""库存成本计算引擎实现。"""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from core.exception import CustomException

from ... import models
from apps.erp.common import COST, MONEY, QTY, quantize
from .repository import CostRepositoryMixin
from .reversals import CostReversalMixin
from .types import (
    CostAdjustmentRequest,
    CostMovementRequest,
    CostPostingResult,
    CostRevaluationRequest,
    CostType,
)


class InventoryCostEngine(CostReversalMixin, CostRepositoryMixin):
    """负责永续移动平均、成本调整、重新计价和成本冲销。"""

    def __init__(self, db: AsyncSession):
        """绑定当前业务事务。"""

        self.db = db

    async def post_movement(self, request: CostMovementRequest) -> CostPostingResult:
        """计算一条库存收发的移动平均成本并更新成本余额。"""

        existing = await self._existing_result(request.idempotency_key)
        if existing:
            return existing
        if request.direction not in (-1, 1):
            raise CustomException("成本移动方向只能是1或-1")
        quantity = quantize(Decimal(request.quantity), QTY)
        if quantity <= 0:
            raise CustomException("成本移动数量必须大于0")
        if request.cost_type in {CostType.ADJUSTMENT, CostType.REVALUATION, CostType.REVERSAL}:
            raise CustomException("库存收发不能使用调整、重新计价或冲销成本类型")

        balance = await self._lock_balance(request.warehouse_id, request.product_id)
        before_quantity = quantize(Decimal(balance.quantity), QTY)
        before_value = quantize(Decimal(balance.inventory_value), MONEY)
        before_cost = quantize(Decimal(balance.average_cost), COST)
        if request.expected_quantity_before is not None and before_quantity != quantize(
            Decimal(request.expected_quantity_before), QTY
        ):
            raise CustomException("库存数量与成本余额数量不一致，已停止过账")

        if request.direction > 0:
            amount = self._receipt_amount(request, quantity)
            signed_amount = amount
            after_quantity = quantize(before_quantity + quantity, QTY)
            after_value = quantize(before_value + amount, MONEY)
            if after_quantity:
                after_cost = quantize(after_value / after_quantity, COST)
            else:
                after_cost = quantize(
                    Decimal(request.unit_cost or (amount / quantity)), COST
                )
            provisional = before_quantity < 0
        else:
            amount = quantize(quantity * before_cost, MONEY)
            signed_amount = -amount
            after_quantity = quantize(before_quantity - quantity, QTY)
            after_value = quantize(before_value - amount, MONEY)
            after_cost = before_cost
            provisional = before_quantity <= 0 or after_quantity < 0

        balance.quantity = after_quantity
        balance.inventory_value = after_value
        balance.average_cost = after_cost
        balance.needs_revaluation = bool(balance.needs_revaluation or provisional)
        balance.last_cost_at = request.occurred_at
        ledger = models.ErpInventoryCostLedger(
            cost_no=request.cost_no[:80],
            idempotency_key=request.idempotency_key,
            cost_type=request.cost_type.value,
            source_type=request.source_type,
            source_id=request.source_id,
            source_no=request.source_no,
            source_line_id=request.source_line_id,
            cost_role=request.cost_role,
            posting_version=request.posting_version,
            stock_movement_id=None,
            reversal_of_id=None,
            warehouse_id=request.warehouse_id,
            product_id=request.product_id,
            quantity=request.direction * quantity,
            amount=signed_amount,
            balance_quantity_before=before_quantity,
            balance_quantity_after=after_quantity,
            balance_value_before=before_value,
            balance_value_after=after_value,
            average_cost_before=before_cost,
            average_cost_after=after_cost,
            provisional=provisional,
            occurred_at=request.occurred_at,
            operator_id=request.operator_id,
            remark=request.remark,
        )
        return self._result(ledger, balance)

    async def attach_stock_movement(
        self, result: CostPostingResult, stock_movement_id: int
    ) -> models.ErpInventoryCostLedger:
        """将待写入成本流水绑定到已经生成的库存流水。"""

        ledger = result.ledger
        if result.is_replay:
            if ledger.stock_movement_id != stock_movement_id:
                raise CustomException("成本幂等流水与库存流水不匹配")
            return ledger
        ledger.stock_movement_id = stock_movement_id
        self.db.add(ledger)
        await self.db.flush()
        result.balance.last_cost_ledger_id = ledger.id
        return ledger

    async def adjust(self, request: CostAdjustmentRequest) -> CostPostingResult:
        """按正负调整金额改变库存价值但不改变库存数量。"""

        amount = quantize(Decimal(request.amount), MONEY)
        if not amount:
            raise CustomException("成本调整金额不能为0")
        existing = await self._existing_result(request.idempotency_key)
        if existing:
            return existing
        inventory_balance = await self._lock_inventory_balance(
            request.warehouse_id, request.product_id
        )
        return await self._post_value_change(
            request=request,
            cost_type=CostType.ADJUSTMENT,
            delta=amount,
            locked_inventory_balance=inventory_balance,
        )

    async def revalue(self, request: CostRevaluationRequest) -> CostPostingResult:
        """按目标平均成本重新计算并调整当前库存价值。"""

        target_cost = quantize(Decimal(request.target_average_cost), COST)
        if target_cost < 0:
            raise CustomException("目标平均成本不能小于0")
        existing = await self._existing_result(request.idempotency_key)
        if existing:
            return existing
        inventory_balance = await self._lock_inventory_balance(
            request.warehouse_id, request.product_id
        )
        balance = await self._lock_balance(request.warehouse_id, request.product_id)
        target_value = quantize(Decimal(balance.quantity) * target_cost, MONEY)
        delta = quantize(target_value - Decimal(balance.inventory_value), MONEY)
        return await self._post_value_change(
            request=request,
            cost_type=CostType.REVALUATION,
            delta=delta,
            locked_balance=balance,
            locked_inventory_balance=inventory_balance,
            target_cost=target_cost,
        )


    async def _post_value_change(
        self,
        request: CostAdjustmentRequest | CostRevaluationRequest,
        cost_type: CostType,
        delta: Decimal,
        locked_balance: models.ErpInventoryCostBalance | None = None,
        locked_inventory_balance: models.ErpInventoryBalance | None = None,
        target_cost: Decimal | None = None,
    ) -> CostPostingResult:
        """写入成本调整或重新计价产生的价值变动。"""

        existing = await self._existing_result(request.idempotency_key)
        if existing:
            return existing
        balance = locked_balance or await self._lock_balance(
            request.warehouse_id, request.product_id
        )
        before_quantity = quantize(Decimal(balance.quantity), QTY)
        before_value = quantize(Decimal(balance.inventory_value), MONEY)
        before_cost = quantize(Decimal(balance.average_cost), COST)
        after_value = quantize(before_value + delta, MONEY)
        after_cost = (
            quantize(target_cost, COST)
            if target_cost is not None
            else quantize(after_value / before_quantity, COST)
            if before_quantity
            else Decimal("0.000000")
        )
        balance.inventory_value = after_value
        balance.average_cost = after_cost
        if cost_type == CostType.REVALUATION:
            balance.needs_revaluation = False
        balance.last_cost_at = request.occurred_at
        ledger = models.ErpInventoryCostLedger(
            cost_no=request.cost_no[:80],
            idempotency_key=request.idempotency_key,
            cost_type=cost_type.value,
            source_type=request.source_type,
            source_id=request.source_id,
            source_no=request.source_no,
            source_line_id=request.source_line_id,
            cost_role=request.cost_role,
            posting_version=request.posting_version,
            stock_movement_id=None,
            reversal_of_id=None,
            warehouse_id=request.warehouse_id,
            product_id=request.product_id,
            quantity=Decimal("0.000000"),
            amount=delta,
            balance_quantity_before=before_quantity,
            balance_quantity_after=before_quantity,
            balance_value_before=before_value,
            balance_value_after=after_value,
            average_cost_before=before_cost,
            average_cost_after=after_cost,
            provisional=False,
            occurred_at=request.occurred_at,
            operator_id=request.operator_id,
            remark=request.remark,
        )
        self.db.add(ledger)
        await self.db.flush()
        balance.last_cost_ledger_id = ledger.id
        await self._mirror_inventory_balance(balance, locked_inventory_balance)
        return self._result(ledger, balance)


    @staticmethod
    def _receipt_amount(request: CostMovementRequest, quantity: Decimal) -> Decimal:
        """从总金额或单位成本计算标准精度的收入成本。"""

        if request.amount is not None:
            amount = Decimal(request.amount)
        elif request.unit_cost is not None:
            amount = quantity * Decimal(request.unit_cost)
        else:
            raise CustomException("收入类库存移动必须提供成本金额或单位成本")
        if amount < 0:
            raise CustomException("收入成本不能小于0")
        return quantize(amount, MONEY)
