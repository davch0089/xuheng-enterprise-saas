"""库存过账冲销规则。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from core.exception import CustomException

from ... import models
from apps.erp.common import QTY, quantize
from .types import MovementType


class StockReversalMixin:
    """按倒序恢复库存、成本、批次和序列号状态。"""

    async def reverse(
        self,
        source_type: str,
        source_id: int,
        posting_version: int,
        source_no: str,
        operator_id: int | None = None,
        occurred_at: datetime | None = None,
    ) -> list[models.ErpInventoryLedger]:
        """按倒序冲销指定业务版本产生的全部库存流水。"""

        originals = list(
            (
                await self.db.scalars(
                    select(models.ErpInventoryLedger)
                    .where(
                        models.ErpInventoryLedger.business_type == source_type,
                        models.ErpInventoryLedger.business_id == source_id,
                        models.ErpInventoryLedger.posting_version == posting_version,
                        models.ErpInventoryLedger.reversal_of_id.is_(None),
                    )
                    .order_by(models.ErpInventoryLedger.id.desc())
                )
            ).all()
        )
        if not originals:
            raise CustomException("找不到需要冲销的库存流水")
        reversal_keys = [f"REVERSE:{item.id}" for item in originals]
        existing = list(
            (
                await self.db.scalars(
                    select(models.ErpInventoryLedger).where(
                        models.ErpInventoryLedger.idempotency_key.in_(reversal_keys)
                    )
                )
            ).all()
        )
        if existing:
            if len(existing) != len(originals):
                raise CustomException("检测到不完整的冲销流水，请人工检查")
            existing_map = {item.idempotency_key: item for item in existing}
            return [existing_map[key] for key in reversal_keys]

        from apps.erp.finance.services.period import AccountingPeriodService
        await AccountingPeriodService(self.db, operator_id).ensure_open(
            originals[0].occurred_at.date(), "库存与成本冲销"
        )

        pairs = {(item.warehouse_id, item.product_id) for item in originals}
        for warehouse_id, product_id in sorted(pairs):
            last_original_id = max(
                item.id
                for item in originals
                if item.warehouse_id == warehouse_id and item.product_id == product_id
            )
            subsequent = list(
                (
                    await self.db.scalars(
                        select(models.ErpInventoryLedger)
                        .where(
                            models.ErpInventoryLedger.warehouse_id == warehouse_id,
                            models.ErpInventoryLedger.product_id == product_id,
                            models.ErpInventoryLedger.id > last_original_id,
                            models.ErpInventoryLedger.reversal_of_id.is_(None),
                        )
                        .order_by(models.ErpInventoryLedger.id)
                    )
                ).all()
            )
            for later in subsequent:
                reversed_id = await self.db.scalar(
                    select(models.ErpInventoryLedger.id).where(
                        models.ErpInventoryLedger.reversal_of_id == later.id
                    )
                )
                if reversed_id is None:
                    raise CustomException(
                        "该商品已有未冲销的后续库存业务，不能冲销；请先撤销后续单据"
                    )

        balances = {}
        for warehouse_id, product_id in sorted(pairs):
            balances[(warehouse_id, product_id)] = await self._lock_balance(
                warehouse_id, product_id
            )

        now = occurred_at or datetime.now()
        reversals = []
        for original, key in zip(originals, reversal_keys):
            balance = balances[(original.warehouse_id, original.product_id)]
            if quantize(Decimal(balance.quantity), QTY) != quantize(
                Decimal(original.balance_quantity_after), QTY
            ):
                raise CustomException("库存余额与原流水不一致，不能冲销")
            cost_result = await self.cost_engine.reverse_stock_movement(
                stock_movement_id=original.id,
                source_type=source_type,
                source_id=source_id,
                source_no=source_no,
                posting_version=posting_version,
                occurred_at=now,
                operator_id=operator_id,
            )
            balance.quantity = original.balance_quantity_before
            balance.available_quantity = quantize(
                Decimal(balance.available_quantity) - Decimal(original.quantity), QTY
            )
            if Decimal(balance.available_quantity) < -Decimal(balance.reserved_quantity) - Decimal(
                balance.frozen_quantity
            ):
                raise CustomException("库存已被预留或冻结，不能冲销")
            balance.average_cost = cost_result.average_cost_after
            balance.inventory_value = cost_result.value_after
            balance.last_movement_at = now
            if original.batch_no:
                await self._reverse_batch(original)
            reversal = models.ErpInventoryLedger(
                movement_no=self._reversal_movement_no(source_no, original),
                idempotency_key=key,
                movement_type=MovementType.REVERSAL.value,
                business_type=source_type,
                business_no=source_no,
                business_id=source_id,
                business_line_id=original.business_line_id,
                movement_role=f"reverse_{original.movement_role}",
                posting_version=posting_version,
                reversal_of_id=original.id,
                direction=-original.direction,
                warehouse_id=original.warehouse_id,
                product_id=original.product_id,
                quantity=-Decimal(original.quantity),
                amount=cost_result.signed_amount,
                balance_quantity_before=original.balance_quantity_after,
                balance_quantity_after=original.balance_quantity_before,
                average_cost_before=cost_result.average_cost_before,
                average_cost_after=cost_result.average_cost_after,
                batch_no=original.batch_no,
                production_date=original.production_date,
                expiry_date=original.expiry_date,
                serial_numbers=original.serial_numbers,
                occurred_at=now,
                operator_id=operator_id,
            )
            self.db.add(reversal)
            await self.db.flush()
            await self.cost_engine.attach_stock_movement(cost_result, reversal.id)
            await self._reverse_serials(original, reversal)
            reversals.append(reversal)
        return reversals

    @staticmethod
    def _reversal_movement_no(source_no: str, original) -> str:
        """根据原流水生成唯一的冲销流水号。"""

        suffix = f"-R{original.id}"
        return f"{source_no[: max(1, 60 - len(suffix))]}{suffix}"
