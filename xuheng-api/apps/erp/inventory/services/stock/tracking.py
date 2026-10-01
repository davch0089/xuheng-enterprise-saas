"""批次与序列号库存跟踪逻辑。"""

import json
from decimal import Decimal

from sqlalchemy import false, select

from core.exception import CustomException

from ... import models
from apps.erp.common import QTY, quantize
from .types import MovementType


class StockTrackingMixin:
    """为库存过账引擎提供批次和序列号变动能力。"""

    async def _apply_batch(self, movement, direction, quantity, warehouse):
        """应用一条库存移动对应的批次余额变化。"""

        if not movement.batch_no:
            return
        batch = await self.db.scalar(
            select(models.ErpInventoryBatchBalance)
            .where(
                models.ErpInventoryBatchBalance.warehouse_id == movement.warehouse_id,
                models.ErpInventoryBatchBalance.product_id == movement.product_id,
                models.ErpInventoryBatchBalance.batch_no == movement.batch_no,
                models.ErpInventoryBatchBalance.is_delete == false(),
            )
            .with_for_update()
        )
        if batch is None:
            if direction < 0:
                raise CustomException(f"批次 {movement.batch_no} 不存在")
            batch = models.ErpInventoryBatchBalance(
                warehouse_id=movement.warehouse_id,
                product_id=movement.product_id,
                batch_no=movement.batch_no,
                production_date=movement.production_date,
                expiry_date=movement.expiry_date,
                quantity=0,
                reserved_quantity=0,
                frozen_quantity=0,
            )
            self.db.add(batch)
            await self.db.flush()
        elif (
            batch.production_date
            and movement.production_date
            and batch.production_date != movement.production_date
        ) or (
            batch.expiry_date
            and movement.expiry_date
            and batch.expiry_date != movement.expiry_date
        ):
            raise CustomException(f"批次 {movement.batch_no} 的生产日期或有效期不一致")
        after = quantize(Decimal(batch.quantity) + direction * quantity, QTY)
        available = after - Decimal(batch.reserved_quantity) - Decimal(batch.frozen_quantity)
        if direction < 0 and not warehouse.allow_negative_stock and available < 0:
            raise CustomException(f"批次 {movement.batch_no} 可用库存不足")
        batch.quantity = after

    async def _apply_serials(self, request, movement, direction, ledger):
        """校验并更新库存移动涉及的全部序列号。"""

        for serial_no in movement.serial_numbers:
            serial = await self.db.scalar(
                select(models.ErpInventorySerial)
                .where(
                    models.ErpInventorySerial.product_id == movement.product_id,
                    models.ErpInventorySerial.serial_no == serial_no,
                )
                .with_for_update()
            )
            from_status = serial.status if serial else None
            from_warehouse_id = serial.warehouse_id if serial else None
            from_batch_no = serial.batch_no if serial else None
            if direction > 0:
                if serial is None:
                    serial = models.ErpInventorySerial(
                        product_id=movement.product_id,
                        serial_no=serial_no,
                        warehouse_id=movement.warehouse_id,
                        batch_no=movement.batch_no,
                        status="in_stock",
                        source_type=request.source_type,
                        source_id=request.source_id,
                        source_line_id=movement.business_line_id,
                        inbound_receipt_id=(
                            request.source_id if request.source_type == "inbound" else None
                        ),
                        inbound_line_id=(
                            movement.business_line_id
                            if request.source_type == "inbound"
                            else None
                        ),
                        inbound_at=request.occurred_at,
                        last_movement_id=ledger.id,
                    )
                    self.db.add(serial)
                elif (
                    serial.status == "voided"
                    and serial.source_type == request.source_type
                    and serial.source_id == request.source_id
                    and serial.source_line_id == movement.business_line_id
                ):
                    serial.status = "in_stock"
                    serial.warehouse_id = movement.warehouse_id
                    serial.batch_no = movement.batch_no
                    serial.inbound_at = request.occurred_at
                    serial.last_movement_id = ledger.id
                elif (
                    movement.movement_type == MovementType.TRANSFER_IN
                    and serial.status == "outbound"
                    and serial.last_movement_id is not None
                ):
                    transfer_out = await self.db.get(
                        models.ErpInventoryLedger, serial.last_movement_id
                    )
                    if (
                        transfer_out is None
                        or transfer_out.movement_type != MovementType.TRANSFER_OUT.value
                        or transfer_out.business_type
                        not in (request.source_type, "transfer_out")
                        or transfer_out.business_id != request.source_id
                        or transfer_out.business_line_id != movement.business_line_id
                    ):
                        raise CustomException(f"序列号 {serial_no} 缺少对应的调拨出库流水")
                    serial.status = "in_stock"
                    serial.warehouse_id = movement.warehouse_id
                    serial.batch_no = movement.batch_no
                    serial.last_movement_id = ledger.id
                elif (
                    movement.movement_type == MovementType.SALE_RETURN
                    and serial.status == "outbound"
                ):
                    serial.status = "in_stock"
                    serial.warehouse_id = movement.warehouse_id
                    serial.batch_no = movement.batch_no
                    serial.last_movement_id = ledger.id
                elif (
                    movement.movement_type == MovementType.STOCK_GAIN
                    and serial.status == "outbound"
                ):
                    serial.status = "in_stock"
                    serial.warehouse_id = movement.warehouse_id
                    serial.batch_no = movement.batch_no
                    serial.last_movement_id = ledger.id
                else:
                    raise CustomException(f"序列号 {serial_no} 已存在")
            else:
                if (
                    serial is None
                    or serial.status != "in_stock"
                    or serial.warehouse_id != movement.warehouse_id
                ):
                    raise CustomException(f"序列号 {serial_no} 不在当前仓库可用库存中")
                if movement.batch_no and serial.batch_no != movement.batch_no:
                    raise CustomException(
                        f"序列号 {serial_no} 属于批次 {serial.batch_no or '无批次'}，"
                        f"不能从批次 {movement.batch_no} 出库"
                    )
                serial.status = "outbound"
                serial.warehouse_id = None
                serial.batch_no = None
                serial.last_movement_id = ledger.id
            await self.db.flush()
            self.db.add(
                models.ErpInventorySerialMovement(
                    serial_id=serial.id,
                    stock_movement_id=ledger.id,
                    serial_no=serial_no,
                    movement_type=movement.movement_type.value,
                    source_type=request.source_type,
                    source_id=request.source_id,
                    source_no=request.source_no,
                    from_status=from_status,
                    to_status=serial.status,
                    from_warehouse_id=from_warehouse_id,
                    to_warehouse_id=serial.warehouse_id,
                    from_batch_no=from_batch_no,
                    to_batch_no=serial.batch_no,
                    occurred_at=request.occurred_at,
                    operator_id=request.operator_id,
                )
            )

    async def _reverse_batch(self, original):
        """按原库存流水恢复批次余额。"""

        batch = await self.db.scalar(
            select(models.ErpInventoryBatchBalance)
            .where(
                models.ErpInventoryBatchBalance.warehouse_id == original.warehouse_id,
                models.ErpInventoryBatchBalance.product_id == original.product_id,
                models.ErpInventoryBatchBalance.batch_no == original.batch_no,
            )
            .with_for_update()
        )
        if batch is None:
            raise CustomException(f"冲销批次 {original.batch_no} 不存在")
        after = quantize(Decimal(batch.quantity) - Decimal(original.quantity), QTY)
        if after < Decimal(batch.reserved_quantity) + Decimal(batch.frozen_quantity):
            raise CustomException(f"批次 {original.batch_no} 已被预留或冻结，不能冲销")
        batch.quantity = after

    async def _reverse_serials(self, original, reversal):
        """按原库存流水恢复序列号状态。"""

        serial_numbers = json.loads(original.serial_numbers) if original.serial_numbers else []
        for serial_no in serial_numbers:
            serial = await self.db.scalar(
                select(models.ErpInventorySerial)
                .where(
                    models.ErpInventorySerial.product_id == original.product_id,
                    models.ErpInventorySerial.serial_no == serial_no,
                )
                .with_for_update()
            )
            if serial is None:
                raise CustomException(f"冲销序列号 {serial_no} 不存在")
            from_status = serial.status
            from_warehouse_id = serial.warehouse_id
            from_batch_no = serial.batch_no
            original_event = await self.db.scalar(
                select(models.ErpInventorySerialMovement).where(
                    models.ErpInventorySerialMovement.serial_id == serial.id,
                    models.ErpInventorySerialMovement.stock_movement_id == original.id,
                    models.ErpInventorySerialMovement.is_delete == false(),
                )
            )
            if original_event:
                if (
                    serial.status != original_event.to_status
                    or serial.warehouse_id != original_event.to_warehouse_id
                    or serial.batch_no != original_event.to_batch_no
                ):
                    raise CustomException(f"序列号 {serial_no} 当前状态与原流水不一致")
                serial.status = original_event.from_status or "voided"
                serial.warehouse_id = original_event.from_warehouse_id
                serial.batch_no = original_event.from_batch_no
            elif original.direction > 0:
                if serial.status != "in_stock":
                    raise CustomException(f"序列号 {serial_no} 已发生后续业务，不能冲销")
                serial.status = "voided"
                serial.warehouse_id = None
                serial.batch_no = None
            else:
                if serial.status != "outbound":
                    raise CustomException(f"序列号 {serial_no} 状态不允许冲销")
                serial.status = "in_stock"
                serial.warehouse_id = original.warehouse_id
                serial.batch_no = original.batch_no
            serial.last_movement_id = reversal.id
            self.db.add(
                models.ErpInventorySerialMovement(
                    serial_id=serial.id,
                    stock_movement_id=reversal.id,
                    serial_no=serial_no,
                    movement_type=MovementType.REVERSAL.value,
                    source_type=reversal.business_type,
                    source_id=reversal.business_id,
                    source_no=reversal.business_no,
                    from_status=from_status,
                    to_status=serial.status,
                    from_warehouse_id=from_warehouse_id,
                    to_warehouse_id=serial.warehouse_id,
                    from_batch_no=from_batch_no,
                    to_batch_no=serial.batch_no,
                    occurred_at=reversal.occurred_at,
                    operator_id=reversal.operator_id,
                )
            )
