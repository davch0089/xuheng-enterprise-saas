"""库存余额查询。"""

from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, case, false, func, or_, select

from apps.erp.master import models as master_models

from .. import models


class BalanceQueryMixin:
    """查询仓库商品余额、可用量和库存价值汇总。"""

    async def balances(
        self,
        page: int,
        limit: int,
        keyword: str | None = None,
        warehouse_id: int | None = None,
        category_id: int | None = None,
        stock_status: str | None = None,
    ):
        """分页查询库存余额并计算库存价值和预警汇总。"""

        page, limit = self._page(page, limit)
        balance = models.ErpInventoryBalance
        product = master_models.ErpProduct
        warehouse = master_models.ErpWarehouse
        unit = master_models.ErpUnit
        category = master_models.ErpProductCategory
        conditions = [balance.is_delete == false(), product.is_delete == false()]
        if keyword:
            pattern = f"%{keyword.strip()}%"
            conditions.append(
                or_(product.code.like(pattern), product.name.like(pattern), product.barcode.like(pattern), product.variant_name.like(pattern), product.specification.like(pattern))
            )
        if warehouse_id:
            conditions.append(balance.warehouse_id == warehouse_id)
        if category_id:
            conditions.append(product.category_id == category_id)
        if stock_status == "positive":
            conditions.append(balance.quantity > 0)
        elif stock_status == "zero":
            conditions.append(balance.quantity == 0)
        elif stock_status == "negative":
            conditions.append(balance.quantity < 0)
        elif stock_status == "low":
            conditions.extend((product.min_stock > 0, balance.available_quantity < product.min_stock))
        joins = (
            select(balance, product, warehouse.name, unit.name, category.name)
            .join(product, product.id == balance.product_id)
            .join(warehouse, warehouse.id == balance.warehouse_id)
            .join(unit, unit.id == product.base_unit_id)
            .join(category, category.id == product.category_id)
            .where(*conditions)
        )
        count = await self.db.scalar(
            select(func.count(balance.id)).join(product, product.id == balance.product_id).where(*conditions)
        )
        summary = (
            await self.db.execute(
                select(
                    func.count(balance.id),
                    func.coalesce(func.sum(balance.inventory_value), 0),
                    func.coalesce(func.sum(case((balance.quantity < 0, 1), else_=0)), 0),
                    func.coalesce(
                        func.sum(case((and_(product.min_stock > 0, balance.available_quantity < product.min_stock), 1), else_=0)),
                        0,
                    ),
                )
                .join(product, product.id == balance.product_id)
                .where(*conditions)
            )
        ).one()
        rows = (
            await self.db.execute(
                joins.order_by(product.code, warehouse.code).offset((page - 1) * limit).limit(limit)
            )
        ).all()
        items = []
        for stock, product_obj, warehouse_name, unit_name, category_name in rows:
            items.append(
                {
                    "id": stock.id,
                    "warehouse_id": stock.warehouse_id,
                    "warehouse_name": warehouse_name,
                    "product_id": product_obj.id,
                    "product_code": product_obj.code,
                    "product_name": product_obj.name,
                    "barcode": product_obj.barcode,
                    "variant_name": product_obj.variant_name,
                    "specification": product_obj.specification,
                    "category_name": category_name,
                    "base_unit_name": unit_name,
                    "quantity": stock.quantity,
                    "available_quantity": stock.available_quantity,
                    "reserved_quantity": stock.reserved_quantity,
                    "frozen_quantity": stock.frozen_quantity,
                    "unit_breakdown": await self._unit_breakdown(product_obj, Decimal(stock.quantity)),
                    "average_cost": stock.average_cost,
                    "inventory_value": stock.inventory_value,
                    "min_stock": product_obj.min_stock,
                    "last_movement_at": stock.last_movement_at,
                }
            )
        return jsonable_encoder(
            {
                "items": items,
                "summary": {
                    "stock_rows": summary[0],
                    "inventory_value": summary[1],
                    "negative_rows": summary[2],
                    "low_stock_rows": summary[3],
                },
            }
        ), count or 0
