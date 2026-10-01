"""采购表单选项、来源单据、应付和付款只读查询。"""

import json
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import false, func, select

from apps.erp.inventory.services.inbound import InventoryService
from apps.erp.master import models as master_models
from apps.erp.master.product_display import sku_snapshot
from apps.erp.finance.services.fund import FundDocumentService
from .. import models


class PurchaseQueryService:
    """为采购管理端提供无副作用的查询模型。"""

    def __init__(self, db):
        """绑定只读数据库会话。"""

        self.db = db
        self.catalog = InventoryService(db)

    async def options(self):
        """返回供应商、仓库、经办人和结算方式选项。"""

        async def values(model):
            """将启用的基础资料转换为统一选择项。"""

            rows = list((await self.db.scalars(select(model).where(model.is_active == True, model.is_delete == false()).order_by(model.code))).all())
            return [{"value": x.id, "label": f"{x.code} {x.name}", "payment_days": getattr(x, "payment_days", 0)} for x in rows]
        return {
            "suppliers": await values(master_models.ErpSupplier),
            "warehouses": await values(master_models.ErpWarehouse),
            "employees": await values(master_models.ErpEmployee),
            "settlement_methods": await values(master_models.ErpSettlementMethod),
            "accounts": await FundDocumentService(self.db).options(),
        }

    async def products(self, keyword=None, warehouse_id=None, limit=100):
        """返回采购商品、参考进价、税率、单位和当前库存。"""

        return await self.catalog.search_products(keyword, warehouse_id, limit)

    async def source_orders(self, supplier_id=None):
        """返回仍有未收数量的已审核采购订单。"""

        conditions = [models.ErpPurchaseOrder.status.in_(("approved", "partial")), models.ErpPurchaseOrder.is_delete == false()]
        if supplier_id:
            conditions.append(models.ErpPurchaseOrder.supplier_id == supplier_id)
        orders = list((await self.db.scalars(select(models.ErpPurchaseOrder).where(*conditions).order_by(models.ErpPurchaseOrder.business_date))).all())
        result = []
        for order in orders:
            item = {key: getattr(order, key) for key in order.get_column_attrs()}
            item["lines"] = []
            lines = list((await self.db.scalars(select(models.ErpPurchaseOrderLine).where(
                models.ErpPurchaseOrderLine.order_id == order.id,
                models.ErpPurchaseOrderLine.received_quantity < models.ErpPurchaseOrderLine.base_quantity,
            ))).all())
            products = {product.id: product for product in (await self.db.scalars(select(master_models.ErpProduct).where(
                master_models.ErpProduct.id.in_({line.product_id for line in lines} or {0})
            ))).all()}
            for line in lines:
                data = {key: getattr(line, key) for key in line.get_column_attrs()}
                product = products.get(line.product_id)
                if product:
                    data["product"] = sku_snapshot(product)
                data["remaining_quantity"] = Decimal(line.base_quantity) - Decimal(line.received_quantity)
                item["lines"].append(data)
            result.append(item)
        return jsonable_encoder(result)

    async def source_receipts(self, supplier_id=None):
        """返回存在可退数量的已审核采购收货单。"""

        conditions = [models.ErpPurchaseReceipt.status == "approved", models.ErpPurchaseReceipt.is_delete == false()]
        if supplier_id:
            conditions.append(models.ErpPurchaseReceipt.supplier_id == supplier_id)
        receipts = list((await self.db.scalars(select(models.ErpPurchaseReceipt).where(*conditions).order_by(models.ErpPurchaseReceipt.business_date))).all())
        result = []
        for receipt in receipts:
            item = {key: getattr(receipt, key) for key in receipt.get_column_attrs()}
            item["lines"] = []
            lines = list((await self.db.scalars(select(models.ErpPurchaseReceiptLine).where(
                models.ErpPurchaseReceiptLine.receipt_id == receipt.id,
                models.ErpPurchaseReceiptLine.returned_quantity < models.ErpPurchaseReceiptLine.base_quantity,
            ))).all())
            products = {product.id: product for product in (await self.db.scalars(select(master_models.ErpProduct).where(
                master_models.ErpProduct.id.in_({line.product_id for line in lines} or {0})
            ))).all()}
            for line in lines:
                data = {key: getattr(line, key) for key in line.get_column_attrs()}
                product = products.get(line.product_id)
                if product:
                    data["product"] = sku_snapshot(product)
                data["serial_numbers"] = json.loads(line.serial_numbers) if line.serial_numbers else []
                data["returnable_quantity"] = Decimal(line.base_quantity) - Decimal(line.returned_quantity)
                item["lines"].append(data)
            result.append(item)
        return jsonable_encoder(result)

    async def payables(self, page, limit, supplier_id=None, status=None):
        """分页查询供应商应付开放项目。"""

        conditions = [models.ErpPayable.is_delete == false()]
        if supplier_id:
            conditions.append(models.ErpPayable.supplier_id == supplier_id)
        if status:
            conditions.append(models.ErpPayable.status == status)
        count = await self.db.scalar(select(func.count(models.ErpPayable.id)).where(*conditions))
        rows = list((await self.db.scalars(select(models.ErpPayable).where(*conditions).order_by(models.ErpPayable.due_date, models.ErpPayable.id).offset((max(page, 1) - 1) * limit).limit(limit))).all())
        return jsonable_encoder([{key: getattr(x, key) for key in x.get_column_attrs()} for x in rows]), count or 0

    async def payments(self, page, limit, supplier_id=None, status=None):
        """分页查询供应商付款单。"""

        conditions = [models.ErpPurchasePayment.is_delete == false()]
        if supplier_id:
            conditions.append(models.ErpPurchasePayment.supplier_id == supplier_id)
        if status:
            conditions.append(models.ErpPurchasePayment.status == status)
        count = await self.db.scalar(select(func.count(models.ErpPurchasePayment.id)).where(*conditions))
        rows = list((await self.db.scalars(select(models.ErpPurchasePayment).where(*conditions).order_by(models.ErpPurchasePayment.payment_date.desc()).offset((max(page, 1) - 1) * limit).limit(limit))).all())
        return jsonable_encoder([{key: getattr(x, key) for key in x.get_column_attrs()} for x in rows]), count or 0
