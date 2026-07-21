"""商品 SPU、SKU 与规格属性的事务服务。"""

from __future__ import annotations

from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exception import CustomException
from .. import models, schemas
from ..crud import MasterDal


class ProductSpuService:
    """统一维护一个商品公共档案及其全部可库存 SKU。"""

    def __init__(self, db: AsyncSession):
        """保存当前请求使用的数据库会话。"""

        self.db = db

    async def list(self, page: int, limit: int, keyword: str | None, is_active: bool | None):
        """分页返回 SPU，并汇总 SKU 数量、库存数量和库存价值。"""

        statement = select(models.ErpProductSpu).where(models.ErpProductSpu.is_delete == false())
        if is_active is not None:
            statement = statement.where(models.ErpProductSpu.is_active == is_active)
        if keyword:
            pattern = f"%{keyword}%"
            sku_match = select(models.ErpProduct.id).where(
                models.ErpProduct.spu_id == models.ErpProductSpu.id,
                models.ErpProduct.is_delete == false(),
                or_(
                    models.ErpProduct.code.like(pattern),
                    models.ErpProduct.name.like(pattern),
                    models.ErpProduct.barcode.like(pattern),
                    models.ErpProduct.variant_name.like(pattern),
                ),
            ).exists()
            statement = statement.where(
                or_(models.ErpProductSpu.code.like(pattern), models.ErpProductSpu.name.like(pattern), sku_match)
            )
        count = await self.db.scalar(select(func.count()).select_from(statement.subquery()))
        statement = statement.order_by(models.ErpProductSpu.code).offset((page - 1) * limit).limit(limit)
        spus = list((await self.db.scalars(statement)).all())
        if not spus:
            return [], int(count or 0)

        spu_ids = [item.id for item in spus]
        skus = list((await self.db.scalars(select(models.ErpProduct).where(
            models.ErpProduct.spu_id.in_(spu_ids), models.ErpProduct.is_delete == false()
        ))).all())
        sku_ids = [item.id for item in skus]
        quantities, values = {}, {}
        if sku_ids:
            from apps.erp.inventory import models as inventory_models

            rows = (await self.db.execute(
                select(
                    inventory_models.ErpInventoryBalance.product_id,
                    func.sum(inventory_models.ErpInventoryBalance.quantity),
                    func.sum(inventory_models.ErpInventoryBalance.inventory_value),
                )
                .where(inventory_models.ErpInventoryBalance.product_id.in_(sku_ids))
                .group_by(inventory_models.ErpInventoryBalance.product_id)
            )).all()
            quantities = {product_id: quantity or Decimal(0) for product_id, quantity, _ in rows}
            values = {product_id: value or Decimal(0) for product_id, _, value in rows}

        result = []
        for spu in spus:
            children = [item for item in skus if item.spu_id == spu.id]
            row = self._columns(spu)
            row.update(
                sku_count=len(children),
                stock_quantity=sum((quantities.get(item.id, Decimal(0)) for item in children), Decimal(0)),
                inventory_value=sum((values.get(item.id, Decimal(0)) for item in children), Decimal(0)),
                skus=[self._sku_summary(item, quantities.get(item.id), values.get(item.id)) for item in children],
            )
            result.append(row)
        return jsonable_encoder(result), int(count or 0)

    async def detail(self, spu_id: int):
        """返回 SPU、全部 SKU 及每个 SKU 的规格属性。"""

        spu = await self._get_spu(spu_id)
        skus = list((await self.db.scalars(
            select(models.ErpProduct)
            .where(models.ErpProduct.spu_id == spu_id, models.ErpProduct.is_delete == false())
            .order_by(models.ErpProduct.is_default_sku.desc(), models.ErpProduct.code)
        )).all())
        attribute_map = await self._attribute_map([item.id for item in skus])
        result = self._columns(spu)
        result["skus"] = [
            {**self._columns(sku), "attributes": attribute_map.get(sku.id, [])}
            for sku in skus
        ]
        return jsonable_encoder(result)

    async def save(self, data: schemas.ProductSpuInput, spu_id: int | None = None):
        """新增或修改商品档案，并在同一事务中同步其 SKU 和属性组合。"""

        await self._ensure_category(data.category_id)
        await self._ensure_unique_spu_code(data.code, spu_id)
        if spu_id:
            spu = await self._get_spu(spu_id, lock=True)
        else:
            spu = models.ErpProductSpu()
            self.db.add(spu)
        for field in ("code", "name", "category_id", "brand", "is_active", "remark"):
            setattr(spu, field, getattr(data, field))
        await self.db.flush()

        current = {
            item.id: item
            for item in (await self.db.scalars(
                select(models.ErpProduct)
                .where(models.ErpProduct.spu_id == spu.id, models.ErpProduct.is_delete == false())
                .with_for_update()
            )).all()
        }
        incoming_ids = {item.id for item in data.skus if item.id is not None}
        if not incoming_ids.issubset(current):
            raise CustomException("包含不属于当前商品的 SKU")
        removed = [item for item_id, item in current.items() if item_id not in incoming_ids]
        for sku in removed:
            await self._ensure_sku_removable(sku.id)
            sku.is_delete = True

        default_index = next((index for index, item in enumerate(data.skus) if item.is_default_sku), 0)
        prepared = []
        variant_keys = {}
        for index, sku_input in enumerate(data.skus):
            values = sku_input.model_dump(exclude={"id", "attributes"})
            await MasterDal(self.db, models.ErpProduct).prepare_product_units(values)
            variant_key = self._variant_key(sku_input.attributes, sku_input.code)
            if variant_key in variant_keys:
                raise CustomException(
                    f"SKU {variant_keys[variant_key]} 与 {sku_input.code} 的规格组合重复"
                )
            variant_keys[variant_key] = sku_input.code
            variant_name = (sku_input.variant_name or "").strip()
            if not variant_name or (
                not sku_input.attributes and variant_name == "默认规格" and len(data.skus) > 1
            ):
                variant_name = self._variant_name(sku_input.attributes)
                if not sku_input.attributes and len(data.skus) > 1:
                    variant_name = (sku_input.specification or "").strip() or sku_input.code
            prepared.append((sku_input, values, variant_key, variant_name, index == default_index))

        await self._ensure_unique_skus(prepared, incoming_ids)
        for sku_input, values, variant_key, variant_name, is_default in prepared:
            sku = current.get(sku_input.id) if sku_input.id else models.ErpProduct(spu_id=spu.id)
            if sku_input.id:
                await self._ensure_immutable_sku_fields(sku, values)
            else:
                self.db.add(sku)
            values.update(
                spu_id=spu.id,
                name=spu.name if variant_name == "默认规格" else f"{spu.name} / {variant_name}",
                category_id=spu.category_id,
                brand=spu.brand,
                variant_name=variant_name,
                variant_key=variant_key,
                is_default_sku=is_default,
            )
            for field, value in values.items():
                setattr(sku, field, value)
            await self.db.flush()
            await self._sync_attributes(sku.id, sku_input.attributes)
        await self.db.flush()
        return await self.detail(spu.id)

    async def delete(self, spu_id: int):
        """删除从未被业务引用的 SPU 及 SKU；有业务历史时要求改为停用。"""

        spu = await self._get_spu(spu_id, lock=True)
        skus = list((await self.db.scalars(select(models.ErpProduct).where(
            models.ErpProduct.spu_id == spu.id, models.ErpProduct.is_delete == false()
        ).with_for_update())).all())
        for sku in skus:
            await self._ensure_sku_removable(sku.id)
        for sku in skus:
            sku.is_delete = True
        spu.is_delete = True
        await self.db.flush()

    async def attribute_options(self):
        """返回已有属性和值，供 SKU 编辑器自动补全。"""

        attributes = list((await self.db.scalars(select(models.ErpProductAttribute).where(
            models.ErpProductAttribute.is_delete == false(), models.ErpProductAttribute.is_active == True
        ).order_by(models.ErpProductAttribute.order, models.ErpProductAttribute.name))).all())
        values = list((await self.db.scalars(select(models.ErpProductAttributeValue).where(
            models.ErpProductAttributeValue.is_delete == false(), models.ErpProductAttributeValue.is_active == True
        ).order_by(models.ErpProductAttributeValue.order, models.ErpProductAttributeValue.value))).all())
        return [
            {"name": item.name, "values": [value.value for value in values if value.attribute_id == item.id]}
            for item in attributes
        ]

    async def _sync_attributes(self, product_id: int, items):
        """重建 SKU 属性关联，并复用已经存在的属性定义和值。"""

        await self.db.execute(delete(models.ErpProductSkuAttribute).where(
            models.ErpProductSkuAttribute.product_id == product_id
        ))
        for order, item in enumerate(items):
            attribute = await self.db.scalar(select(models.ErpProductAttribute).where(
                func.lower(models.ErpProductAttribute.name) == item.name.casefold()
            ))
            if attribute is None:
                attribute = models.ErpProductAttribute(name=item.name, order=order)
                self.db.add(attribute)
                await self.db.flush()
            elif attribute.is_delete:
                attribute.is_delete = False
                attribute.is_active = True
            value = await self.db.scalar(select(models.ErpProductAttributeValue).where(
                models.ErpProductAttributeValue.attribute_id == attribute.id,
                func.lower(models.ErpProductAttributeValue.value) == item.value.casefold(),
            ))
            if value is None:
                value = models.ErpProductAttributeValue(attribute_id=attribute.id, value=item.value, order=order)
                self.db.add(value)
                await self.db.flush()
            elif value.is_delete:
                value.is_delete = False
                value.is_active = True
            self.db.add(models.ErpProductSkuAttribute(
                product_id=product_id, attribute_id=attribute.id, value_id=value.id
            ))

    async def _attribute_map(self, product_ids: list[int]):
        """批量组装 SKU 属性，避免详情接口逐个查询。"""

        if not product_ids:
            return {}
        rows = (await self.db.execute(
            select(
                models.ErpProductSkuAttribute.product_id,
                models.ErpProductAttribute.name,
                models.ErpProductAttributeValue.value,
            )
            .join(models.ErpProductAttribute, models.ErpProductAttribute.id == models.ErpProductSkuAttribute.attribute_id)
            .join(models.ErpProductAttributeValue, models.ErpProductAttributeValue.id == models.ErpProductSkuAttribute.value_id)
            .where(models.ErpProductSkuAttribute.product_id.in_(product_ids))
            .order_by(models.ErpProductAttribute.order, models.ErpProductAttribute.name)
        )).all()
        result = {}
        for product_id, name, value in rows:
            result.setdefault(product_id, []).append({"name": name, "value": value})
        return result

    async def _ensure_unique_skus(self, prepared, current_ids: set[int]):
        """检查 SKU 编码和非空条码在整个系统中全局唯一。"""

        codes = [item[0].code for item in prepared]
        barcodes = [item[0].barcode for item in prepared if item[0].barcode]
        statement = select(models.ErpProduct.code, models.ErpProduct.barcode).where(
            models.ErpProduct.is_delete == false(),
            or_(models.ErpProduct.code.in_(codes), models.ErpProduct.barcode.in_(barcodes or ["__NONE__"])),
        )
        if current_ids:
            statement = statement.where(models.ErpProduct.id.not_in(current_ids))
        if (await self.db.execute(statement)).first():
            raise CustomException("SKU 编码或条形码已存在")

    async def _ensure_immutable_sku_fields(self, sku, values):
        """有库存历史后禁止修改会破坏计量或跟踪连续性的 SKU 字段。"""

        protected = ("base_unit_id", "unit_group_id", "multi_unit_enabled", "batch_enabled", "serial_enabled", "costing_method")
        if all(getattr(sku, field) == values.get(field) for field in protected):
            return
        from apps.erp.inventory import models as inventory_models

        movement = await self.db.scalar(select(inventory_models.ErpInventoryLedger.id).where(
            inventory_models.ErpInventoryLedger.product_id == sku.id
        ).limit(1))
        if movement is not None:
            raise CustomException("SKU 已产生库存流水，不能修改单位、成本方法或批次/序列号设置")

    async def _ensure_sku_removable(self, product_id: int):
        """确认 SKU 没有库存和业务引用，防止删除后历史单据失去商品。"""

        from apps.erp.inventory import models as inventory_models
        from apps.erp.purchase import models as purchase_models
        from apps.erp.sales import models as sales_models

        references = (
            inventory_models.ErpInventoryLedger,
            inventory_models.ErpInboundReceiptLine,
            inventory_models.ErpBillOfMaterial,
            inventory_models.ErpBillOfMaterialLine,
            inventory_models.ErpAssemblyOrderLine,
            inventory_models.ErpStockTransferLine,
            inventory_models.ErpInventoryCountLine,
            inventory_models.ErpOtherStockOrderLine,
            purchase_models.ErpPurchaseOrderLine,
            purchase_models.ErpPurchaseReceiptLine,
            purchase_models.ErpPurchaseReturnLine,
            sales_models.ErpSalesOrderLine,
            sales_models.ErpSalesDeliveryLine,
            sales_models.ErpSalesReturnLine,
        )
        for model in references:
            field = (
                model.component_product_id
                if model is inventory_models.ErpBillOfMaterialLine
                else model.product_id
            )
            if await self.db.scalar(select(model.id).where(field == product_id).limit(1)) is not None:
                raise CustomException("SKU 已被业务或库存引用，不能删除，请改为停用")

    async def _ensure_category(self, category_id: int):
        """校验商品分类存在且处于启用状态。"""

        category = await self.db.scalar(select(models.ErpProductCategory.id).where(
            models.ErpProductCategory.id == category_id,
            models.ErpProductCategory.is_delete == false(),
            models.ErpProductCategory.is_active == True,
        ))
        if category is None:
            raise CustomException("商品分类不存在或已停用")

    async def _ensure_unique_spu_code(self, code: str, spu_id: int | None):
        """校验 SPU 编码全局唯一。"""

        statement = select(models.ErpProductSpu.id).where(
            models.ErpProductSpu.code == code, models.ErpProductSpu.is_delete == false()
        )
        if spu_id:
            statement = statement.where(models.ErpProductSpu.id != spu_id)
        if await self.db.scalar(statement) is not None:
            raise CustomException("SPU 编码已存在")

    async def _get_spu(self, spu_id: int, lock: bool = False):
        """读取存在的 SPU，并可选择加行锁。"""

        statement = select(models.ErpProductSpu).where(
            models.ErpProductSpu.id == spu_id, models.ErpProductSpu.is_delete == false()
        )
        if lock:
            statement = statement.with_for_update()
        spu = await self.db.scalar(statement)
        if spu is None:
            raise CustomException("商品 SPU 不存在")
        return spu

    @staticmethod
    def _variant_key(attributes, sku_code: str) -> str:
        """生成规格组合键；未配置规格属性时使用 SKU 编码保持各 SKU 独立。"""

        if not attributes:
            return f"__SKU__:{sku_code.strip().casefold()}"
        return "|".join(sorted(
            f"{item.name.strip().casefold()}={item.value.strip().casefold()}" for item in attributes
        ))

    @staticmethod
    def _variant_name(attributes) -> str:
        """根据属性值生成便于业务人员识别的规格名称。"""

        return " / ".join(item.value for item in attributes) if attributes else "默认规格"

    @staticmethod
    def _columns(obj) -> dict:
        """把 ORM 实体的数据库字段转换成普通字典。"""

        return {field: getattr(obj, field) for field in obj.get_column_attrs()}

    def _sku_summary(self, sku, quantity=None, inventory_value=None) -> dict:
        """构造列表展开行所需的精简 SKU 信息。"""

        return jsonable_encoder({
            **self._columns(sku),
            "stock_quantity": quantity or Decimal(0),
            "inventory_value": inventory_value or Decimal(0),
        })
