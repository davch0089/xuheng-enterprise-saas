"""销售订单库存预留服务。"""

from decimal import Decimal

from sqlalchemy import false, select

from apps.erp.common import QTY, quantize
from apps.erp.inventory import models as inventory_models
from apps.erp.master import models as master_models
from core.exception import CustomException

from .. import models


class StockReservationService:
    """维护订单预留记录和库存余额中的预留、可用数量。"""

    def __init__(self, db):
        """绑定当前业务事务。"""

        self.db = db

    async def reserve_order(self, order, lines):
        """为已审核订单的全部未交数量建立库存预留。"""

        for line in lines:
            quantity = quantize(Decimal(line.base_quantity) - Decimal(line.delivered_quantity), QTY)
            if quantity <= 0:
                continue
            balance, warehouse = await self._lock_balance(line.warehouse_id, line.product_id)
            if not warehouse.allow_negative_stock and Decimal(balance.available_quantity) < quantity:
                raise CustomException(f"商品ID {line.product_id} 可用库存不足，无法审核订单")
            balance.reserved_quantity = quantize(Decimal(balance.reserved_quantity) + quantity, QTY)
            balance.available_quantity = quantize(Decimal(balance.available_quantity) - quantity, QTY)
            reservation = await self.db.scalar(
                select(models.ErpStockReservation).where(
                    models.ErpStockReservation.source_type == "sales_order",
                    models.ErpStockReservation.source_line_id == line.id,
                )
            )
            if reservation is None:
                reservation = models.ErpStockReservation(
                    source_type="sales_order",
                    source_id=order.id,
                    source_line_id=line.id,
                    warehouse_id=line.warehouse_id,
                    product_id=line.product_id,
                    quantity=quantity,
                    released_quantity=0,
                    status="active",
                )
                self.db.add(reservation)
            else:
                reservation.warehouse_id = line.warehouse_id
                reservation.product_id = line.product_id
                reservation.quantity = quantity
                reservation.released_quantity = 0
                reservation.status = "active"
        await self.db.flush()

    async def release_for_delivery(self, order_line_id: int, quantity: Decimal):
        """在订单出库前释放对应数量，使库存引擎可以正常扣减。"""

        reservation = await self._lock_reservation(order_line_id)
        quantity = quantize(quantity, QTY)
        remaining = quantize(
            Decimal(reservation.quantity) - Decimal(reservation.released_quantity), QTY
        )
        if remaining < quantity:
            raise CustomException("销售订单剩余预留数量不足")
        balance, _ = await self._lock_balance(reservation.warehouse_id, reservation.product_id)
        balance.reserved_quantity = quantize(Decimal(balance.reserved_quantity) - quantity, QTY)
        balance.available_quantity = quantize(Decimal(balance.available_quantity) + quantity, QTY)
        reservation.released_quantity = quantize(
            Decimal(reservation.released_quantity) + quantity, QTY
        )
        reservation.status = "released" if reservation.released_quantity == reservation.quantity else "partial"

    async def restore_from_delivery(self, order_line_id: int, quantity: Decimal):
        """反审核出库单时恢复订单预留。"""

        reservation = await self._lock_reservation(order_line_id)
        quantity = quantize(quantity, QTY)
        if Decimal(reservation.released_quantity) < quantity:
            raise CustomException("订单预留释放记录不足，不能恢复")
        balance, warehouse = await self._lock_balance(reservation.warehouse_id, reservation.product_id)
        if not warehouse.allow_negative_stock and Decimal(balance.available_quantity) < quantity:
            raise CustomException("当前可用库存不足，无法恢复订单预留")
        balance.reserved_quantity = quantize(Decimal(balance.reserved_quantity) + quantity, QTY)
        balance.available_quantity = quantize(Decimal(balance.available_quantity) - quantity, QTY)
        reservation.released_quantity = quantize(
            Decimal(reservation.released_quantity) - quantity, QTY
        )
        reservation.status = "active" if reservation.released_quantity == 0 else "partial"

    async def cancel_order(self, order_id: int):
        """反审核订单时释放所有尚未使用的库存预留。"""

        reservations = list(
            (
                await self.db.scalars(
                    select(models.ErpStockReservation)
                    .where(
                        models.ErpStockReservation.source_type == "sales_order",
                        models.ErpStockReservation.source_id == order_id,
                        models.ErpStockReservation.is_delete == false(),
                    )
                    .with_for_update()
                )
            ).all()
        )
        for reservation in reservations:
            remaining = quantize(
                Decimal(reservation.quantity) - Decimal(reservation.released_quantity), QTY
            )
            if remaining:
                balance, _ = await self._lock_balance(
                    reservation.warehouse_id, reservation.product_id
                )
                balance.reserved_quantity = quantize(
                    Decimal(balance.reserved_quantity) - remaining, QTY
                )
                balance.available_quantity = quantize(
                    Decimal(balance.available_quantity) + remaining, QTY
                )
            reservation.released_quantity = reservation.quantity
            reservation.status = "cancelled"

    async def _lock_reservation(self, order_line_id: int):
        """锁定指定订单行的有效预留记录。"""

        reservation = await self.db.scalar(
            select(models.ErpStockReservation)
            .where(
                models.ErpStockReservation.source_type == "sales_order",
                models.ErpStockReservation.source_line_id == order_line_id,
                models.ErpStockReservation.is_delete == false(),
            )
            .with_for_update()
        )
        if reservation is None or reservation.status == "cancelled":
            raise CustomException("找不到销售订单库存预留")
        return reservation

    async def _lock_balance(self, warehouse_id: int, product_id: int):
        """锁定库存余额并读取仓库负库存策略。"""

        balance = await self.db.scalar(
            select(inventory_models.ErpInventoryBalance)
            .where(
                inventory_models.ErpInventoryBalance.warehouse_id == warehouse_id,
                inventory_models.ErpInventoryBalance.product_id == product_id,
                inventory_models.ErpInventoryBalance.is_delete == false(),
            )
            .with_for_update()
        )
        warehouse = await self.db.get(master_models.ErpWarehouse, warehouse_id)
        if balance is None or warehouse is None:
            raise CustomException("库存余额或仓库不存在")
        return balance, warehouse
