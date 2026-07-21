"""入库商品搜索、单位换算和明细预处理。"""

import json
from datetime import timedelta
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, false, or_, select

from apps.erp.master import models as master_models
from apps.erp.master.product_display import sku_display_spec, sku_label
from core.exception import CustomException

from ... import models, schemas
from apps.erp.common import COST, MONEY, QTY, quantize


class InboundCatalogMixin:
    """为入库服务提供商品目录和明细校验能力。"""

    async def product_units(self, product: master_models.ErpProduct) -> list[dict]:
        """返回商品可选单位及其相对主单位换算率。"""

        unit_ids = {product.base_unit_id}
        items = []
        if product.multi_unit_enabled and product.unit_group_id:
            items = list(
                (
                    await self.db.scalars(
                        select(master_models.ErpUnitGroupItem)
                        .where(
                            master_models.ErpUnitGroupItem.group_id == product.unit_group_id,
                            master_models.ErpUnitGroupItem.is_delete == false(),
                        )
                        .order_by(
                            master_models.ErpUnitGroupItem.order,
                            master_models.ErpUnitGroupItem.id,
                        )
                    )
                ).all()
            )
            unit_ids.update(item.unit_id for item in items)
        units = {
            item.id: item
            for item in (
                await self.db.scalars(
                    select(master_models.ErpUnit).where(
                        master_models.ErpUnit.id.in_(unit_ids),
                        master_models.ErpUnit.is_delete == false(),
                    )
                )
            ).all()
        }
        base = units.get(product.base_unit_id)
        if base is None:
            raise CustomException(f"商品 {product.code} 的主单位不存在")
        result = [
            {
                "unit_id": base.id,
                "unit_name": base.name,
                "unit_code": base.code,
                "to_base_rate": Decimal("1"),
                "decimal_places": base.decimal_places,
                "level": 0,
            }
        ]
        item_map = {item.id: item for item in items}
        rate_cache: dict[int, Decimal] = {}
        level_cache: dict[int, int] = {}

        def calculate(item_id: int, visiting: set[int] | None = None):
            """递归计算多层子单位相对主单位的换算率。"""

            if item_id in rate_cache:
                return rate_cache[item_id], level_cache[item_id]
            visiting = visiting or set()
            if item_id in visiting:
                raise CustomException("多单位方案存在循环层级")
            visiting.add(item_id)
            item = item_map[item_id]
            if item.parent_id is None:
                parent_rate, level = Decimal("1"), 1
            elif item.parent_id in item_map:
                parent_rate, parent_level = calculate(item.parent_id, visiting)
                level = parent_level + 1
            else:
                raise CustomException("多单位方案的上级单位不存在")
            rate = parent_rate / Decimal(item.factor)
            rate_cache[item_id], level_cache[item_id] = rate, level
            visiting.remove(item_id)
            return rate, level

        for item in items:
            unit = units.get(item.unit_id)
            if unit:
                rate, level = calculate(item.id)
                result.append(
                    {
                        "unit_id": unit.id,
                        "unit_name": unit.name,
                        "unit_code": unit.code,
                        "to_base_rate": rate,
                        "decimal_places": unit.decimal_places,
                        "level": level,
                    }
                )
        return result

    async def search_products(
        self, keyword: str | None, warehouse_id: int | None, limit: int = 30
    ):
        """搜索可入库商品并返回指定仓库的当前库存。"""

        balance_join = and_(
            models.ErpInventoryBalance.product_id == master_models.ErpProduct.id,
            models.ErpInventoryBalance.warehouse_id == warehouse_id,
            models.ErpInventoryBalance.is_delete == false(),
        )
        sql = (
            select(
                master_models.ErpProduct,
                models.ErpInventoryBalance.quantity,
                master_models.ErpProductSpu.code,
                master_models.ErpProductSpu.name,
            )
            .outerjoin(models.ErpInventoryBalance, balance_join)
            .join(
                master_models.ErpProductSpu,
                master_models.ErpProductSpu.id == master_models.ErpProduct.spu_id,
            )
            .where(
                master_models.ErpProduct.is_active == True,
                master_models.ErpProduct.is_delete == false(),
                master_models.ErpProductSpu.is_active == True,
                master_models.ErpProductSpu.is_delete == false(),
            )
            .order_by(master_models.ErpProduct.code)
            .limit(min(max(limit, 1), 100))
        )
        if keyword:
            pattern = f"%{keyword.strip()}%"
            sql = sql.where(
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
        rows = (await self.db.execute(sql)).all()
        result = []
        for product, stock, spu_code, spu_name in rows:
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
                    "batch_enabled": product.batch_enabled,
                    "serial_enabled": product.serial_enabled,
                    "shelf_life_days": product.shelf_life_days,
                    "default_purchase_price": product.default_purchase_price,
                    "tax_rate": product.tax_rate,
                    "stock_quantity": stock or Decimal("0"),
                    "base_unit_id": product.base_unit_id,
                    "units": await self.product_units(product),
                }
            )
        return jsonable_encoder(result)

    async def _active(self, model, data_id: int, label: str):
        """读取有效基础资料，不存在或停用时中止业务。"""

        obj = await self.db.scalar(
            select(model).where(
                model.id == data_id,
                model.is_active == True,
                model.is_delete == false(),
            )
        )
        if obj is None:
            raise CustomException(f"{label}不存在或已停用")
        return obj

    async def _prepare_lines(self, data: schemas.InboundReceiptInput):
        """校验入库明细并计算主单位数量、成本和有效期。"""

        await self._active(master_models.ErpWarehouse, data.warehouse_id, "默认仓库")
        if data.supplier_id:
            await self._active(master_models.ErpSupplier, data.supplier_id, "供应商")
        if data.employee_id:
            await self._active(master_models.ErpEmployee, data.employee_id, "经办人")
        prepared = []
        serials_in_document: set[tuple[int, str]] = set()
        for index, input_line in enumerate(data.lines, 1):
            warehouse_id = input_line.warehouse_id or data.warehouse_id
            await self._active(master_models.ErpWarehouse, warehouse_id, f"第{index}行仓库")
            product = await self._active(
                master_models.ErpProduct, input_line.product_id, f"第{index}行商品"
            )
            units = {item["unit_id"]: item for item in await self.product_units(product)}
            selected_unit = units.get(input_line.unit_id)
            if selected_unit is None:
                raise CustomException(f"第{index}行所选单位不属于该商品")
            rate = Decimal(selected_unit["to_base_rate"])
            quantity = quantize(input_line.quantity, QTY)
            base_quantity = quantize(quantity * rate, QTY)
            if base_quantity <= 0:
                raise CustomException(f"第{index}行折算后的主单位数量必须大于0")
            unit_price = quantize(input_line.unit_price, COST)
            amount = quantize(quantity * unit_price, MONEY)
            base_unit_cost = quantize(amount / base_quantity, COST)
            production_date = input_line.production_date
            expiry_date = input_line.expiry_date
            batch_no = input_line.batch_no
            if product.batch_enabled:
                if not batch_no:
                    raise CustomException(f"第{index}行商品启用了批次管理，请填写批次号")
                if production_date and not expiry_date and product.shelf_life_days is not None:
                    expiry_date = production_date + timedelta(days=product.shelf_life_days)
                if production_date and expiry_date and expiry_date < production_date:
                    raise CustomException(f"第{index}行有效期不能早于生产日期")
            else:
                batch_no = None
                production_date = None
                expiry_date = None
            serial_numbers = input_line.serial_numbers if product.serial_enabled else []
            if product.serial_enabled:
                if base_quantity != base_quantity.to_integral_value():
                    raise CustomException(f"第{index}行序列号商品的主单位数量必须为整数")
                if len(serial_numbers) != int(base_quantity):
                    raise CustomException(
                        f"第{index}行应录入 {int(base_quantity)} 个序列号，"
                        f"当前为 {len(serial_numbers)} 个"
                    )
                for serial in serial_numbers:
                    key = (product.id, serial)
                    if key in serials_in_document:
                        raise CustomException(f"序列号 {serial} 在本单重复")
                    serials_in_document.add(key)
            prepared.append(
                {
                    "line_no": index,
                    "product_id": product.id,
                    "warehouse_id": warehouse_id,
                    "unit_id": input_line.unit_id,
                    "unit_to_base_rate": rate,
                    "quantity": quantity,
                    "base_quantity": base_quantity,
                    "unit_price": unit_price,
                    "amount": amount,
                    "base_unit_cost": base_unit_cost,
                    "batch_no": batch_no,
                    "production_date": production_date,
                    "expiry_date": expiry_date,
                    "serial_numbers": (
                        json.dumps(serial_numbers, ensure_ascii=False)
                        if serial_numbers
                        else None
                    ),
                    "remark": input_line.remark,
                }
            )
        return prepared
