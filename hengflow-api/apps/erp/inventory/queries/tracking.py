"""批次和序列号库存查询。"""

from datetime import date, timedelta
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import case, false, func, or_, select

from apps.erp.master import models as master_models

from .. import models


class TrackingQueryMixin:
    """查询批次有效期和序列号库存状态。"""

    async def batches(
        self,
        page: int,
        limit: int,
        keyword: str | None = None,
        warehouse_id: int | None = None,
        expiry_status: str | None = None,
    ):
        """分页查询批次库存、可用数量和有效期状态。"""

        page, limit = self._page(page, limit)
        batch = models.ErpInventoryBatchBalance
        product = master_models.ErpProduct
        warehouse = master_models.ErpWarehouse
        conditions = [batch.is_delete == false(), product.is_delete == false()]
        if keyword:
            pattern = f"%{keyword.strip()}%"
            conditions.append(or_(batch.batch_no.like(pattern), product.code.like(pattern), product.name.like(pattern), product.barcode.like(pattern), product.variant_name.like(pattern), product.specification.like(pattern)))
        if warehouse_id:
            conditions.append(batch.warehouse_id == warehouse_id)
        today = date.today()
        if expiry_status == "expired":
            conditions.append(batch.expiry_date < today)
        elif expiry_status == "near":
            conditions.extend((batch.expiry_date >= today, batch.expiry_date <= today + timedelta(days=30)))
        elif expiry_status == "normal":
            conditions.append(or_(batch.expiry_date.is_(None), batch.expiry_date > today + timedelta(days=30)))
        base = (
            select(batch, product.code, product.name, product.barcode, product.variant_name, product.specification, warehouse.name)
            .join(product, product.id == batch.product_id)
            .join(warehouse, warehouse.id == batch.warehouse_id)
            .where(*conditions)
        )
        count = await self.db.scalar(select(func.count(batch.id)).join(product, product.id == batch.product_id).where(*conditions))
        rows = (await self.db.execute(base.order_by(batch.expiry_date, product.code).offset((page - 1) * limit).limit(limit))).all()
        items = []
        for item, code, name, barcode, variant_name, specification, warehouse_name in rows:
            items.append(
                {
                    "id": item.id,
                    "warehouse_id": item.warehouse_id,
                    "product_id": item.product_id,
                    "warehouse_name": warehouse_name,
                    "product_code": code,
                    "product_name": name,
                    "barcode": barcode,
                    "variant_name": variant_name,
                    "specification": specification,
                    "batch_no": item.batch_no,
                    "production_date": item.production_date,
                    "expiry_date": item.expiry_date,
                    "quantity": item.quantity,
                    "reserved_quantity": item.reserved_quantity,
                    "frozen_quantity": item.frozen_quantity,
                    "available_quantity": Decimal(item.quantity) - Decimal(item.reserved_quantity) - Decimal(item.frozen_quantity),
                    "days_to_expiry": (item.expiry_date - today).days if item.expiry_date else None,
                }
            )
        return jsonable_encoder(items), count or 0

    async def serials(
        self,
        page: int,
        limit: int,
        keyword: str | None = None,
        warehouse_id: int | None = None,
        status: str | None = None,
    ):
        """分页查询序列号的仓库位置和库存状态。"""

        page, limit = self._page(page, limit)
        serial = models.ErpInventorySerial
        product = master_models.ErpProduct
        warehouse = master_models.ErpWarehouse
        receipt = models.ErpInboundReceipt
        conditions = [serial.is_delete == false()]
        if keyword:
            pattern = f"%{keyword.strip()}%"
            conditions.append(or_(serial.serial_no.like(pattern), product.code.like(pattern), product.name.like(pattern), product.barcode.like(pattern), product.variant_name.like(pattern), product.specification.like(pattern), receipt.receipt_no.like(pattern)))
        if warehouse_id:
            conditions.append(serial.warehouse_id == warehouse_id)
        if status:
            conditions.append(serial.status == status)
        base = (
            select(serial, product.code, product.name, product.barcode, product.variant_name, product.specification, warehouse.name, receipt.receipt_no)
            .join(product, product.id == serial.product_id)
            .outerjoin(warehouse, warehouse.id == serial.warehouse_id)
            .outerjoin(receipt, receipt.id == serial.inbound_receipt_id)
            .where(*conditions)
        )
        count = await self.db.scalar(
            select(func.count(serial.id)).join(product, product.id == serial.product_id).outerjoin(receipt, receipt.id == serial.inbound_receipt_id).where(*conditions)
        )
        rows = (await self.db.execute(base.order_by(serial.inbound_at.desc(), serial.id.desc()).offset((page - 1) * limit).limit(limit))).all()
        items = [
            {
                "id": item.id,
                "serial_no": item.serial_no,
                "status": item.status,
                "warehouse_name": warehouse_name,
                "product_code": code,
                "product_name": name,
                "barcode": barcode,
                "variant_name": variant_name,
                "specification": specification,
                "inbound_receipt_no": receipt_no,
                "inbound_at": item.inbound_at,
                "batch_no": item.batch_no,
                "source_type": item.source_type,
                "source_id": item.source_id,
            }
            for item, code, name, barcode, variant_name, specification, warehouse_name, receipt_no in rows
        ]
        return jsonable_encoder(items), count or 0

    async def fifo_batches(self, warehouse_id: int, product_id: int, quantity: Decimal):
        """按先到期先出、再先进先出顺序推荐满足出库数量的批次。"""

        today = date.today()
        rows = list(
            (
                await self.db.scalars(
                    select(models.ErpInventoryBatchBalance)
                    .where(
                        models.ErpInventoryBatchBalance.warehouse_id == warehouse_id,
                        models.ErpInventoryBatchBalance.product_id == product_id,
                        models.ErpInventoryBatchBalance.is_delete == false(),
                        models.ErpInventoryBatchBalance.quantity
                        > models.ErpInventoryBatchBalance.reserved_quantity
                        + models.ErpInventoryBatchBalance.frozen_quantity,
                    )
                    .order_by(
                        case((models.ErpInventoryBatchBalance.expiry_date.is_(None), 1), else_=0),
                        models.ErpInventoryBatchBalance.expiry_date,
                        models.ErpInventoryBatchBalance.production_date,
                        models.ErpInventoryBatchBalance.id,
                    )
                )
            ).all()
        )
        remaining = Decimal(quantity)
        result = []
        for index, batch in enumerate(rows, 1):
            available = Decimal(batch.quantity) - Decimal(batch.reserved_quantity) - Decimal(batch.frozen_quantity)
            suggested = min(max(remaining, Decimal(0)), available)
            result.append(
                {
                    "priority": index,
                    "batch_no": batch.batch_no,
                    "production_date": batch.production_date,
                    "expiry_date": batch.expiry_date,
                    "days_to_expiry": (batch.expiry_date - today).days if batch.expiry_date else None,
                    "expired": bool(batch.expiry_date and batch.expiry_date < today),
                    "available_quantity": available,
                    "suggested_quantity": suggested,
                }
            )
            remaining -= suggested
        return jsonable_encoder({"items": result, "shortage_quantity": max(remaining, Decimal(0))})

    async def serial_history(self, serial_id: int):
        """返回指定序列号从首次入库到当前状态的完整移动履历。"""

        serial = await self.db.get(models.ErpInventorySerial, serial_id)
        if serial is None or serial.is_delete:
            return []
        movement = models.ErpInventorySerialMovement
        from_warehouse = master_models.ErpWarehouse
        to_warehouse = master_models.ErpWarehouse
        rows = list(
            (
                await self.db.execute(
                    select(movement)
                    .where(movement.serial_id == serial_id, movement.is_delete == false())
                    .order_by(movement.occurred_at, movement.id)
                )
            ).scalars().all()
        )
        warehouse_ids = {x.from_warehouse_id for x in rows if x.from_warehouse_id} | {x.to_warehouse_id for x in rows if x.to_warehouse_id}
        warehouses = {x.id: x.name for x in (await self.db.scalars(select(master_models.ErpWarehouse).where(master_models.ErpWarehouse.id.in_(warehouse_ids or {0})))).all()}
        return jsonable_encoder([
            {
                **{key: getattr(row, key) for key in row.get_column_attrs()},
                "from_warehouse_name": warehouses.get(row.from_warehouse_id),
                "to_warehouse_name": warehouses.get(row.to_warehouse_id),
            }
            for row in rows
        ])
