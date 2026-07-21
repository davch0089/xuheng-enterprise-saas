"""销售单据、商品、应收和收款只读查询。"""

import json

from datetime import date
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import false, func, or_, select

from apps.erp.inventory import models as inventory_models
from apps.erp.inventory.services.inbound import InventoryService
from apps.erp.master import models as master_models
from apps.erp.master.product_display import sku_display_spec, sku_label, sku_snapshot
from apps.erp.finance.services.fund import FundDocumentService

from .. import models


class SalesQueryService:
    """为销售页面提供分页列表、选择项和来源单据查询。"""

    def __init__(self, db):
        """绑定只读数据库会话。"""

        self.db = db

    async def options(self):
        """返回销售单据需要的客户、仓库、职员和结算方式。"""

        async def active_options(model):
            """读取启用基础资料并转换为下拉选项。"""

            rows = (
                await self.db.scalars(
                    select(model).where(
                        model.is_active == True, model.is_delete == false()
                    ).order_by(model.code)
                )
            ).all()
            return [
                {
                    "value": item.id,
                    "label": f"{item.code} {item.name}",
                    "address": getattr(item, "address", None),
                    "payment_days": getattr(item, "payment_days", 0),
                    "credit_limit": getattr(item, "credit_limit", 0),
                }
                for item in rows
            ]

        return jsonable_encoder(
            {
                "customers": await active_options(master_models.ErpCustomer),
                "warehouses": await active_options(master_models.ErpWarehouse),
                "employees": await active_options(master_models.ErpEmployee),
                "settlement_methods": await active_options(
                    master_models.ErpSettlementMethod
                ),
                "accounts": await FundDocumentService(self.db).options(),
            }
        )

    async def products(
        self, keyword: str | None, warehouse_id: int | None, limit: int = 30
    ):
        """搜索销售商品并返回售价、可用库存和单位换算。"""

        conditions = [
            master_models.ErpProduct.is_active == True,
            master_models.ErpProduct.is_delete == false(),
            master_models.ErpProductSpu.is_active == True,
            master_models.ErpProductSpu.is_delete == false(),
        ]
        if keyword:
            pattern = f"%{keyword.strip()}%"
            conditions.append(
                or_(
                    master_models.ErpProduct.code.like(pattern),
                    master_models.ErpProduct.name.like(pattern),
                    master_models.ErpProduct.barcode.like(pattern),
                    master_models.ErpProduct.variant_name.like(pattern),
                    master_models.ErpProduct.specification.like(pattern),
                    master_models.ErpProductSpu.code.like(pattern),
                    master_models.ErpProductSpu.name.like(pattern),
                )
            )
        sql = (
            select(
                master_models.ErpProduct,
                inventory_models.ErpInventoryBalance,
                master_models.ErpProductSpu.code,
                master_models.ErpProductSpu.name,
            )
            .join(
                master_models.ErpProductSpu,
                master_models.ErpProductSpu.id == master_models.ErpProduct.spu_id,
            )
            .outerjoin(
                inventory_models.ErpInventoryBalance,
                (inventory_models.ErpInventoryBalance.product_id == master_models.ErpProduct.id)
                & (inventory_models.ErpInventoryBalance.warehouse_id == warehouse_id),
            )
            .where(*conditions)
            .order_by(master_models.ErpProduct.code)
            .limit(min(max(limit, 1), 100))
        )
        unit_service = InventoryService(self.db)
        result = []
        for product, balance, spu_code, spu_name in (await self.db.execute(sql)).all():
            result.append(
                {
                    "id": product.id,
                    "spu_id": product.spu_id,
                    "spu_code": spu_code,
                    "spu_name": spu_name,
                    "code": product.code,
                    "name": product.name,
                    "barcode": product.barcode,
                    "variant_name": product.variant_name,
                    "specification": product.specification,
                    "display_spec": sku_display_spec(product),
                    "sku_label": sku_label(product),
                    "default_sale_price": product.default_sale_price,
                    "tax_rate": product.tax_rate,
                    "batch_enabled": product.batch_enabled,
                    "serial_enabled": product.serial_enabled,
                    "base_unit_id": product.base_unit_id,
                    "available_quantity": balance.available_quantity if balance else 0,
                    "units": await unit_service.product_units(product),
                }
            )
        return jsonable_encoder(result)

    async def document_list(
        self,
        kind: str,
        page: int,
        limit: int,
        keyword: str | None = None,
        status: str | None = None,
        customer_id: int | None = None,
        date_start: date | None = None,
        date_end: date | None = None,
    ):
        """统一分页查询销售订单、出库单或退货单。"""

        model, number_field = {
            "order": (models.ErpSalesOrder, "order_no"),
            "delivery": (models.ErpSalesDelivery, "delivery_no"),
            "return": (models.ErpSalesReturn, "return_no"),
        }[kind]
        number = getattr(model, number_field)
        conditions = [model.is_delete == false()]
        if keyword:
            conditions.append(number.like(f"%{keyword.strip()}%"))
        if status:
            conditions.append(model.status == status)
        if customer_id:
            conditions.append(model.customer_id == customer_id)
        if date_start:
            conditions.append(model.business_date >= date_start)
        if date_end:
            conditions.append(model.business_date <= date_end)
        count = await self.db.scalar(select(func.count(model.id)).where(*conditions))
        rows = list(
            (
                await self.db.scalars(
                    select(model)
                    .where(*conditions)
                    .order_by(model.business_date.desc(), model.id.desc())
                    .offset((max(page, 1) - 1) * min(max(limit, 1), 100))
                    .limit(min(max(limit, 1), 100))
                )
            ).all()
        )
        customer_ids = {item.customer_id for item in rows}
        customers = {
            item.id: item.name
            for item in (
                await self.db.scalars(
                    select(master_models.ErpCustomer).where(
                        master_models.ErpCustomer.id.in_(customer_ids or {0})
                    )
                )
            ).all()
        }
        result = []
        for row in rows:
            item = {key: getattr(row, key) for key in row.get_column_attrs()}
            item["document_no"] = getattr(row, number_field)
            item["customer_name"] = customers.get(row.customer_id)
            result.append(item)
        return jsonable_encoder(result), count or 0

    async def source_orders(self, customer_id: int | None = None):
        """返回可继续出库的已审核或部分履约销售订单。"""

        conditions = [
            models.ErpSalesOrder.status.in_(("approved", "partial")),
            models.ErpSalesOrder.is_delete == false(),
        ]
        if customer_id:
            conditions.append(models.ErpSalesOrder.customer_id == customer_id)
        orders = list((await self.db.scalars(select(models.ErpSalesOrder).where(*conditions))).all())
        result = []
        for order in orders:
            item = {key: getattr(order, key) for key in order.get_column_attrs()}
            item["lines"] = []
            lines = (
                await self.db.scalars(
                    select(models.ErpSalesOrderLine).where(
                        models.ErpSalesOrderLine.order_id == order.id,
                        models.ErpSalesOrderLine.delivered_quantity
                        < models.ErpSalesOrderLine.base_quantity,
                    )
                )
            ).all()
            products = {
                product.id: product
                for product in (
                    await self.db.scalars(
                        select(master_models.ErpProduct).where(
                            master_models.ErpProduct.id.in_({line.product_id for line in lines} or {0})
                        )
                    )
                ).all()
            }
            for line in lines:
                data = {key: getattr(line, key) for key in line.get_column_attrs()}
                product = products.get(line.product_id)
                if product:
                    data["product"] = sku_snapshot(product)
                data["remaining_quantity"] = Decimal(line.base_quantity) - Decimal(
                    line.delivered_quantity
                )
                item["lines"].append(data)
            result.append(item)
        return jsonable_encoder(result)

    async def source_deliveries(self, customer_id: int | None = None):
        """返回存在可退商品的已审核销售出库单。"""

        conditions = [
            models.ErpSalesDelivery.status == "approved",
            models.ErpSalesDelivery.is_delete == false(),
        ]
        if customer_id:
            conditions.append(models.ErpSalesDelivery.customer_id == customer_id)
        deliveries = list(
            (await self.db.scalars(select(models.ErpSalesDelivery).where(*conditions))).all()
        )
        result = []
        for delivery in deliveries:
            item = {key: getattr(delivery, key) for key in delivery.get_column_attrs()}
            item["lines"] = []
            lines = (
                await self.db.scalars(
                    select(models.ErpSalesDeliveryLine).where(
                        models.ErpSalesDeliveryLine.delivery_id == delivery.id,
                        models.ErpSalesDeliveryLine.returned_quantity
                        < models.ErpSalesDeliveryLine.base_quantity,
                    )
                )
            ).all()
            products = {
                product.id: product
                for product in (
                    await self.db.scalars(
                        select(master_models.ErpProduct).where(
                            master_models.ErpProduct.id.in_({line.product_id for line in lines} or {0})
                        )
                    )
                ).all()
            }
            for line in lines:
                data = {key: getattr(line, key) for key in line.get_column_attrs()}
                product = products.get(line.product_id)
                if product:
                    data["product"] = sku_snapshot(product)
                data["serial_numbers"] = json.loads(line.serial_numbers) if line.serial_numbers else []
                data["returnable_quantity"] = Decimal(line.base_quantity) - Decimal(
                    line.returned_quantity
                )
                item["lines"].append(data)
            result.append(item)
        return jsonable_encoder(result)

    async def receivables(
        self, page: int, limit: int, customer_id: int | None = None, status: str | None = None
    ):
        """分页查询客户应收开放项目。"""

        conditions = [models.ErpReceivable.is_delete == false()]
        if customer_id:
            conditions.append(models.ErpReceivable.customer_id == customer_id)
        if status:
            conditions.append(models.ErpReceivable.status == status)
        count = await self.db.scalar(
            select(func.count(models.ErpReceivable.id)).where(*conditions)
        )
        rows = list(
            (
                await self.db.scalars(
                    select(models.ErpReceivable)
                    .where(*conditions)
                    .order_by(models.ErpReceivable.due_date, models.ErpReceivable.id)
                    .offset((max(page, 1) - 1) * limit)
                    .limit(limit)
                )
            ).all()
        )
        return jsonable_encoder(
            [{key: getattr(row, key) for key in row.get_column_attrs()} for row in rows]
        ), count or 0

    async def receipt_list(
        self, page: int, limit: int, customer_id: int | None = None, status: str | None = None
    ):
        """分页查询客户收款单。"""

        conditions = [models.ErpSalesReceipt.is_delete == false()]
        if customer_id:
            conditions.append(models.ErpSalesReceipt.customer_id == customer_id)
        if status:
            conditions.append(models.ErpSalesReceipt.status == status)
        count = await self.db.scalar(
            select(func.count(models.ErpSalesReceipt.id)).where(*conditions)
        )
        rows = list(
            (
                await self.db.scalars(
                    select(models.ErpSalesReceipt)
                    .where(*conditions)
                    .order_by(models.ErpSalesReceipt.receipt_date.desc())
                    .offset((max(page, 1) - 1) * limit)
                    .limit(limit)
                )
            ).all()
        )
        return jsonable_encoder(
            [{key: getattr(row, key) for key in row.get_column_attrs()} for row in rows]
        ), count or 0
