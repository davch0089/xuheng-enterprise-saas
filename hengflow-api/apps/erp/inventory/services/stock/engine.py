"""库存数量过账引擎实现。"""

import json
from dataclasses import replace
from decimal import Decimal

from sqlalchemy import false, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.erp.master import models as master_models
from core.exception import CustomException

from ... import models
from apps.erp.common import QTY, quantize
from ..cost import CostMovementRequest, CostType, InventoryCostEngine
from .reversals import StockReversalMixin
from .tracking import StockTrackingMixin
from .types import INBOUND_TYPES, OUTBOUND_TYPES, MovementType, PostingRequest, StockMovement


class StockPostingEngine(StockReversalMixin, StockTrackingMixin):
    """统一处理库存数量、批次、序列号和成本联动过账。"""

    INBOUND_BUSINESS_TYPES = {
        "purchase": MovementType.PURCHASE_IN,
        "other": MovementType.OTHER_IN,
        "stock_gain": MovementType.STOCK_GAIN,
        "production": MovementType.PRODUCTION_IN,
        "transfer": MovementType.TRANSFER_IN,
    }

    def __init__(self, db: AsyncSession):
        """绑定当前业务事务并初始化成本引擎。"""

        self.db = db
        self.cost_engine = InventoryCostEngine(db)

    @classmethod
    def inbound_movement_type(cls, business_type: str) -> MovementType:
        """将入库业务类型转换为标准库存移动类型。"""

        movement_type = cls.INBOUND_BUSINESS_TYPES.get(business_type)
        if movement_type is None:
            raise CustomException(f"不支持的入库业务类型：{business_type}")
        return movement_type

    @staticmethod
    def _idempotency_key(request: PostingRequest, movement: StockMovement) -> str:
        """生成业务版本和明细角色级别的库存幂等键。"""

        return (
            f"POST:{request.source_type}:{request.source_id}:V{request.posting_version}:"
            f"L{movement.business_line_id}:{movement.movement_role}"
        )

    @staticmethod
    def _movement_no(request: PostingRequest, movement: StockMovement) -> str:
        """生成可追溯到业务单据明细的库存流水号。"""

        suffix = f"-V{request.posting_version}-L{movement.business_line_id}-{movement.movement_role}"
        return f"{request.source_no[: max(1, 60 - len(suffix))]}{suffix}"

    async def post(self, request: PostingRequest) -> list[models.ErpInventoryLedger]:
        """在一个事务中完成请求内全部库存移动和成本过账。"""

        if not request.movements:
            raise CustomException("没有可过账的库存移动")
        keys = [self._idempotency_key(request, item) for item in request.movements]
        if len(keys) != len(set(keys)):
            raise CustomException("库存移动的业务行和移动角色不能重复")
        existing = list(
            (
                await self.db.scalars(
                    select(models.ErpInventoryLedger).where(
                        models.ErpInventoryLedger.idempotency_key.in_(keys)
                    )
                )
            ).all()
        )
        if existing:
            if len(existing) != len(keys):
                raise CustomException("检测到不完整的历史过账，请人工检查库存流水")
            existing_map = {item.idempotency_key: item for item in existing}
            return [existing_map[key] for key in keys]

        from apps.erp.finance.services.period import AccountingPeriodService
        await AccountingPeriodService(self.db, request.operator_id).ensure_open(
            request.occurred_at.date(), "库存与成本过账"
        )

        product_ids = {item.product_id for item in request.movements}
        warehouse_ids = {item.warehouse_id for item in request.movements}
        products = {
            item.id: item
            for item in (
                await self.db.scalars(
                    select(master_models.ErpProduct).where(
                        master_models.ErpProduct.id.in_(product_ids),
                        master_models.ErpProduct.is_delete == false(),
                    )
                )
            ).all()
        }
        warehouses = {
            item.id: item
            for item in (
                await self.db.scalars(
                    select(master_models.ErpWarehouse).where(
                        master_models.ErpWarehouse.id.in_(warehouse_ids),
                        master_models.ErpWarehouse.is_delete == false(),
                    )
                )
            ).all()
        }
        if len(products) != len(product_ids):
            raise CustomException("过账商品不存在")
        if len(warehouses) != len(warehouse_ids):
            raise CustomException("过账仓库不存在")

        balances = {}
        for warehouse_id, product_id in sorted(
            {(item.warehouse_id, item.product_id) for item in request.movements}
        ):
            balances[(warehouse_id, product_id)] = await self._lock_balance(
                warehouse_id, product_id
            )

        result = []
        transfer_costs: dict[int, Decimal] = {}
        for movement, key in zip(request.movements, keys):
            if (
                movement.movement_type == MovementType.TRANSFER_IN
                and movement.amount is None
                and movement.unit_cost is None
            ):
                transfer_amount = transfer_costs.get(movement.business_line_id)
                if transfer_amount is None:
                    raise CustomException("调拨入库必须排在同一业务行的调拨出库之后")
                movement = replace(movement, amount=transfer_amount)
            product = products[movement.product_id]
            warehouse = warehouses[movement.warehouse_id]
            self._validate_movement(movement, product)
            balance = balances[(movement.warehouse_id, movement.product_id)]
            ledger = await self._apply_movement(
                request, movement, key, product, warehouse, balance
            )
            if movement.movement_type == MovementType.TRANSFER_OUT:
                transfer_costs[movement.business_line_id] = abs(Decimal(ledger.amount))
            result.append(ledger)
        await self.db.flush()
        return result


    async def _lock_balance(self, warehouse_id: int, product_id: int):
        """创建并锁定仓库商品库存余额，防止并发覆盖。"""

        await self.db.execute(
            mysql_insert(models.ErpInventoryBalance)
            .values(
                warehouse_id=warehouse_id,
                product_id=product_id,
                quantity=0,
                available_quantity=0,
                reserved_quantity=0,
                frozen_quantity=0,
                average_cost=0,
                inventory_value=0,
            )
            .on_duplicate_key_update(id=models.ErpInventoryBalance.id)
        )
        return await self.db.scalar(
            select(models.ErpInventoryBalance)
            .where(
                models.ErpInventoryBalance.warehouse_id == warehouse_id,
                models.ErpInventoryBalance.product_id == product_id,
                models.ErpInventoryBalance.is_delete == false(),
            )
            .with_for_update()
        )

    def _validate_movement(self, movement: StockMovement, product):
        """校验移动类型、数量以及批次和序列号必填规则。"""

        if movement.movement_type not in INBOUND_TYPES | OUTBOUND_TYPES:
            raise CustomException(f"不支持的库存移动类型：{movement.movement_type}")
        if Decimal(movement.quantity) <= 0:
            raise CustomException("库存移动数量必须大于0")
        serials = list(movement.serial_numbers)
        if len(serials) != len(set(serials)):
            raise CustomException("同一库存移动中存在重复序列号")
        if product.batch_enabled and not movement.batch_no:
            raise CustomException(f"批次商品 {product.code} 必须提供批次号")
        if product.serial_enabled:
            quantity = Decimal(movement.quantity)
            if quantity != quantity.to_integral_value() or len(serials) != int(quantity):
                raise CustomException(f"序列号商品 {product.code} 的序列号数量必须等于主单位数量")

    async def _apply_movement(
        self, request, movement, key, product, warehouse, balance
    ):
        """应用单条库存移动并关联对应的成本流水。"""

        inbound = movement.movement_type in INBOUND_TYPES
        direction = 1 if inbound else -1
        quantity = quantize(Decimal(movement.quantity), QTY)
        before_quantity = Decimal(balance.quantity)
        before_available = Decimal(balance.available_quantity)
        after_quantity = quantize(before_quantity + direction * quantity, QTY)
        after_available = quantize(before_available + direction * quantity, QTY)
        if not inbound and not warehouse.allow_negative_stock and before_available < quantity:
            raise CustomException(f"{warehouse.name} 的商品 {product.code} 可用库存不足")
        cost_result = await self.cost_engine.post_movement(
            CostMovementRequest(
                idempotency_key=f"COST:{key}",
                cost_no=f"{self._movement_no(request, movement)}-C",
                cost_type=self._cost_type(movement.movement_type),
                source_type=request.source_type,
                source_id=request.source_id,
                source_no=request.source_no,
                source_line_id=movement.business_line_id,
                cost_role=movement.movement_role,
                posting_version=request.posting_version,
                warehouse_id=movement.warehouse_id,
                product_id=movement.product_id,
                direction=direction,
                quantity=quantity,
                amount=movement.amount,
                unit_cost=movement.unit_cost,
                expected_quantity_before=before_quantity,
                occurred_at=request.occurred_at,
                operator_id=request.operator_id,
            )
        )
        signed_quantity = direction * quantity
        balance.quantity = after_quantity
        balance.available_quantity = after_available
        balance.average_cost = cost_result.average_cost_after
        balance.inventory_value = cost_result.value_after
        balance.last_movement_at = request.occurred_at
        await self._apply_batch(movement, direction, quantity, warehouse)
        ledger = models.ErpInventoryLedger(
            movement_no=self._movement_no(request, movement),
            idempotency_key=key,
            movement_type=movement.movement_type.value,
            business_type=request.source_type,
            business_no=request.source_no,
            business_id=request.source_id,
            business_line_id=movement.business_line_id,
            movement_role=movement.movement_role,
            posting_version=request.posting_version,
            reversal_of_id=None,
            direction=direction,
            warehouse_id=movement.warehouse_id,
            product_id=movement.product_id,
            quantity=signed_quantity,
            amount=cost_result.signed_amount,
            balance_quantity_before=before_quantity,
            balance_quantity_after=after_quantity,
            average_cost_before=cost_result.average_cost_before,
            average_cost_after=cost_result.average_cost_after,
            batch_no=movement.batch_no,
            production_date=movement.production_date,
            expiry_date=movement.expiry_date,
            serial_numbers=(
                json.dumps(list(movement.serial_numbers), ensure_ascii=False)
                if movement.serial_numbers
                else None
            ),
            occurred_at=request.occurred_at,
            operator_id=request.operator_id,
        )
        self.db.add(ledger)
        await self.db.flush()
        await self.cost_engine.attach_stock_movement(cost_result, ledger.id)
        await self._apply_serials(request, movement, direction, ledger)
        return ledger

    @staticmethod
    def _cost_type(movement_type: MovementType) -> CostType:
        """将库存移动类型映射为成本流水类型。"""

        if movement_type == MovementType.TRANSFER_IN:
            return CostType.TRANSFER_IN
        if movement_type == MovementType.TRANSFER_OUT:
            return CostType.TRANSFER_OUT
        if movement_type in INBOUND_TYPES:
            return CostType.RECEIPT
        return CostType.ISSUE
