"""入库单只读查询。"""

import json
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import false, func, select

from apps.erp.master import models as master_models
from apps.erp.master.product_display import sku_snapshot
from core.exception import CustomException

from ... import models


class InboundReadMixin:
    """提供入库单详情、列表和基础资料名称批量读取。"""

    async def receipt_detail(self, receipt_id: int):
        """返回入库单、商品、单位和当前库存的完整编辑数据。"""

        receipt = await self.db.scalar(
            select(models.ErpInboundReceipt).where(
                models.ErpInboundReceipt.id == receipt_id, models.ErpInboundReceipt.is_delete == false()
            )
        )
        if receipt is None:
            raise CustomException("入库单不存在")
        lines = list(
            (
                await self.db.scalars(
                    select(models.ErpInboundReceiptLine)
                    .where(models.ErpInboundReceiptLine.receipt_id == receipt_id)
                    .order_by(models.ErpInboundReceiptLine.line_no)
                )
            ).all()
        )
        products = {
            item.id: item
            for item in (
                await self.db.scalars(
                    select(master_models.ErpProduct).where(
                        master_models.ErpProduct.id.in_([line.product_id for line in lines] or [0])
                    )
                )
            ).all()
        }
        result = {key: getattr(receipt, key) for key in models.ErpInboundReceipt.get_column_attrs()}
        result["lines"] = []
        for line in lines:
            item = {key: getattr(line, key) for key in models.ErpInboundReceiptLine.get_column_attrs()}
            item["serial_numbers"] = json.loads(line.serial_numbers) if line.serial_numbers else []
            product = products.get(line.product_id)
            if product:
                stock_quantity = await self.db.scalar(
                    select(models.ErpInventoryBalance.quantity).where(
                        models.ErpInventoryBalance.warehouse_id == line.warehouse_id,
                        models.ErpInventoryBalance.product_id == line.product_id,
                        models.ErpInventoryBalance.is_delete == false(),
                    )
                )
                item["product"] = {
                    **sku_snapshot(product),
                    "batch_enabled": product.batch_enabled,
                    "serial_enabled": product.serial_enabled,
                    "shelf_life_days": product.shelf_life_days,
                    "stock_quantity": stock_quantity or Decimal("0"),
                    "units": await self.product_units(product),
                }
            result["lines"].append(item)
        return jsonable_encoder(result)

    async def receipt_list(
        self,
        page: int,
        limit: int,
        keyword: str | None,
        status: str | None,
        business_type: str | None,
        date_start,
        date_end,
    ):
        """按状态、类型、日期和关键字分页查询入库单。"""

        conditions = [models.ErpInboundReceipt.is_delete == false()]
        if keyword:
            conditions.append(models.ErpInboundReceipt.receipt_no.like(f"%{keyword}%"))
        if status:
            conditions.append(models.ErpInboundReceipt.status == status)
        if business_type:
            conditions.append(models.ErpInboundReceipt.business_type == business_type)
        if date_start:
            conditions.append(models.ErpInboundReceipt.receipt_date >= date_start)
        if date_end:
            conditions.append(models.ErpInboundReceipt.receipt_date <= date_end)
        total = await self.db.scalar(select(func.count(models.ErpInboundReceipt.id)).where(*conditions))
        receipts = list(
            (
                await self.db.scalars(
                    select(models.ErpInboundReceipt)
                    .where(*conditions)
                    .order_by(models.ErpInboundReceipt.receipt_date.desc(), models.ErpInboundReceipt.id.desc())
                    .offset((page - 1) * limit)
                    .limit(limit)
                )
            ).all()
        )
        supplier_ids = {item.supplier_id for item in receipts if item.supplier_id}
        warehouse_ids = {item.warehouse_id for item in receipts}
        employee_ids = {item.employee_id for item in receipts if item.employee_id}
        suppliers = await self._name_map(master_models.ErpSupplier, supplier_ids)
        warehouses = await self._name_map(master_models.ErpWarehouse, warehouse_ids)
        employees = await self._name_map(master_models.ErpEmployee, employee_ids)
        result = []
        for receipt in receipts:
            item = {key: getattr(receipt, key) for key in models.ErpInboundReceipt.get_column_attrs()}
            item.update(
                supplier_name=suppliers.get(receipt.supplier_id),
                warehouse_name=warehouses.get(receipt.warehouse_id),
                employee_name=employees.get(receipt.employee_id),
            )
            result.append(item)
        return jsonable_encoder(result), total or 0

    async def _name_map(self, model, ids: set[int]):
        """批量取得基础资料 ID 与名称的映射。"""

        if not ids:
            return {}
        return {item.id: item.name for item in (await self.db.scalars(select(model).where(model.id.in_(ids)))).all()}

