"""库存收发流水查询。"""

from datetime import date, datetime, time, timedelta

from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, false, func, or_, select

from apps.erp.master import models as master_models

from .. import models


class MovementQueryMixin:
    """按业务、商品、仓库和日期查询库存收发流水。"""

    async def movements(
        self,
        page: int,
        limit: int,
        keyword: str | None = None,
        warehouse_id: int | None = None,
        product_id: int | None = None,
        direction: int | None = None,
        date_start: date | None = None,
        date_end: date | None = None,
    ):
        """分页查询库存收发流水及其过账前后快照。"""

        page, limit = self._page(page, limit)
        ledger = models.ErpInventoryLedger
        product = master_models.ErpProduct
        warehouse = master_models.ErpWarehouse
        receipt = models.ErpInboundReceipt
        conditions = [ledger.is_delete == false()]
        if keyword:
            pattern = f"%{keyword.strip()}%"
            conditions.append(
                or_(
                    ledger.movement_no.like(pattern),
                    ledger.business_no.like(pattern),
                    receipt.receipt_no.like(pattern),
                    product.code.like(pattern),
                    product.name.like(pattern),
                    product.barcode.like(pattern),
                    product.variant_name.like(pattern),
                    product.specification.like(pattern),
                )
            )
        if warehouse_id:
            conditions.append(ledger.warehouse_id == warehouse_id)
        if product_id:
            conditions.append(ledger.product_id == product_id)
        if direction in (-1, 1):
            conditions.append(ledger.direction == direction)
        if date_start:
            conditions.append(ledger.occurred_at >= datetime.combine(date_start, time.min))
        if date_end:
            conditions.append(ledger.occurred_at < datetime.combine(date_end + timedelta(days=1), time.min))
        join_sql = (
            select(ledger, product.code, product.name, product.barcode, product.variant_name, product.specification, warehouse.name, receipt.receipt_no)
            .join(product, product.id == ledger.product_id)
            .join(warehouse, warehouse.id == ledger.warehouse_id)
            .outerjoin(receipt, and_(receipt.id == ledger.business_id, ledger.business_type.in_(("inbound", "inbound_reversal"))))
            .where(*conditions)
        )
        count = await self.db.scalar(
            select(func.count(ledger.id))
            .join(product, product.id == ledger.product_id)
            .outerjoin(receipt, and_(receipt.id == ledger.business_id, ledger.business_type.in_(("inbound", "inbound_reversal"))))
            .where(*conditions)
        )
        rows = (
            await self.db.execute(join_sql.order_by(ledger.occurred_at.desc(), ledger.id.desc()).offset((page - 1) * limit).limit(limit))
        ).all()
        items = [
            {
                "id": item.id,
                "movement_no": item.movement_no,
                "movement_type": item.movement_type,
                "business_type": item.business_type,
                "business_no": item.business_no or receipt_no or str(item.business_id),
                "direction": item.direction,
                "warehouse_name": warehouse_name,
                "product_code": product_code,
                "product_name": product_name,
                "barcode": barcode,
                "variant_name": variant_name,
                "specification": specification,
                "quantity": item.quantity,
                "amount": item.amount,
                "balance_quantity_before": item.balance_quantity_before,
                "balance_quantity_after": item.balance_quantity_after,
                "average_cost_before": item.average_cost_before,
                "average_cost_after": item.average_cost_after,
                "occurred_at": item.occurred_at,
            }
            for item, product_code, product_name, barcode, variant_name, specification, warehouse_name, receipt_no in rows
        ]
        return jsonable_encoder(items), count or 0
