"""成本余额的加锁、镜像和幂等读取操作。"""

from decimal import Decimal

from sqlalchemy import false, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from core.exception import CustomException

from ... import models
from apps.erp.common import MONEY, QTY, quantize
from .types import CostPostingResult


class CostRepositoryMixin:
    """封装成本引擎访问成本余额与库存成本镜像的公共操作。"""

    async def _lock_balance(self, warehouse_id: int, product_id: int):
        """创建并行锁定指定仓库商品的成本余额。"""

        inventory_balance = await self.db.scalar(
            select(models.ErpInventoryBalance)
            .where(
                models.ErpInventoryBalance.warehouse_id == warehouse_id,
                models.ErpInventoryBalance.product_id == product_id,
                models.ErpInventoryBalance.is_delete == false(),
            )
            .with_for_update()
        )
        opening_quantity = Decimal(inventory_balance.quantity) if inventory_balance else Decimal(0)
        opening_value = Decimal(inventory_balance.inventory_value) if inventory_balance else Decimal(0)
        opening_cost = Decimal(inventory_balance.average_cost) if inventory_balance else Decimal(0)
        await self.db.execute(
            mysql_insert(models.ErpInventoryCostBalance)
            .values(
                warehouse_id=warehouse_id,
                product_id=product_id,
                quantity=opening_quantity,
                inventory_value=opening_value,
                average_cost=opening_cost,
                needs_revaluation=False,
            )
            .on_duplicate_key_update(id=models.ErpInventoryCostBalance.id)
        )
        return await self.db.scalar(
            select(models.ErpInventoryCostBalance)
            .where(
                models.ErpInventoryCostBalance.warehouse_id == warehouse_id,
                models.ErpInventoryCostBalance.product_id == product_id,
                models.ErpInventoryCostBalance.is_delete == false(),
            )
            .with_for_update()
        )

    async def _lock_inventory_balance(self, warehouse_id: int, product_id: int):
        """锁定与成本余额对应的库存数量余额。"""

        inventory_balance = await self.db.scalar(
            select(models.ErpInventoryBalance)
            .where(
                models.ErpInventoryBalance.warehouse_id == warehouse_id,
                models.ErpInventoryBalance.product_id == product_id,
                models.ErpInventoryBalance.is_delete == false(),
            )
            .with_for_update()
        )
        if inventory_balance is None:
            raise CustomException("成本余额缺少对应的库存余额")
        return inventory_balance

    async def _mirror_inventory_balance(
        self,
        cost_balance,
        inventory_balance: models.ErpInventoryBalance | None = None,
    ):
        """将独立成本余额同步到库存查询使用的成本镜像。"""

        inventory_balance = inventory_balance or await self._lock_inventory_balance(
            cost_balance.warehouse_id, cost_balance.product_id
        )
        if quantize(Decimal(inventory_balance.quantity), QTY) != quantize(
            Decimal(cost_balance.quantity), QTY
        ):
            raise CustomException("库存数量与成本余额数量不一致，不能调整成本")
        inventory_balance.average_cost = cost_balance.average_cost
        inventory_balance.inventory_value = cost_balance.inventory_value

    async def _existing_result(self, idempotency_key: str):
        """按幂等键读取已生成的成本流水及当前余额。"""

        ledger = await self.db.scalar(
            select(models.ErpInventoryCostLedger).where(
                models.ErpInventoryCostLedger.idempotency_key == idempotency_key
            )
        )
        if ledger is None:
            return None
        balance = await self.db.scalar(
            select(models.ErpInventoryCostBalance).where(
                models.ErpInventoryCostBalance.warehouse_id == ledger.warehouse_id,
                models.ErpInventoryCostBalance.product_id == ledger.product_id,
            )
        )
        result = self._result(ledger, balance)
        result.is_replay = True
        return result

    @staticmethod
    def _result(ledger, balance):
        """根据成本流水和余额构造统一过账结果。"""

        return CostPostingResult(
            ledger=ledger,
            balance=balance,
            quantity_before=Decimal(ledger.balance_quantity_before),
            quantity_after=Decimal(ledger.balance_quantity_after),
            value_before=Decimal(ledger.balance_value_before),
            value_after=Decimal(ledger.balance_value_after),
            average_cost_before=Decimal(ledger.average_cost_before),
            average_cost_after=Decimal(ledger.average_cost_after),
            signed_amount=Decimal(ledger.amount),
        )
