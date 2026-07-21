from fastapi.encoders import jsonable_encoder
from sqlalchemy import false, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.crud import DalBase
from core.exception import CustomException


class MasterDal(DalBase):
    def __init__(self, db: AsyncSession, model):
        super().__init__(db=db, model=model)

    async def out_dict(self, obj, v_options=None, v_return_obj=False, v_schema=None):
        if v_options:
            obj = await self.get_data(obj.id, v_options=v_options)
        if v_return_obj:
            return obj
        data = {field: getattr(obj, field) for field in self.model.get_column_attrs()}
        return jsonable_encoder(data)

    async def get_list(self, page: int, limit: int, keyword: str | None, is_active: bool | None, search_fields):
        sql = select(self.model).where(self.model.is_delete == false())
        if keyword:
            expressions = [getattr(self.model, field).like(f"%{keyword}%") for field in search_fields]
            sql = sql.where(or_(*expressions))
        if is_active is not None and hasattr(self.model, "is_active"):
            sql = sql.where(self.model.is_active == is_active)
        order_field = getattr(self.model, "code", getattr(self.model, "id"))
        return await self.get_datas(
            page=page, limit=limit, v_start_sql=sql, v_order_field=order_field.key,
            v_return_count=True, v_schema=None
        )

    async def ensure_unique(self, data: dict, data_id: int | None = None):
        checks = []
        if data.get("code") is not None and hasattr(self.model, "code"):
            checks.append(("code", data["code"], "编码已存在"))
        if self.model.__tablename__ == "erp_product" and data.get("barcode"):
            checks.append(("barcode", data["barcode"], "商品条码已存在"))
        if self.model.__tablename__ == "erp_unit_group" and data.get("name"):
            checks.append(("name", data["name"], "多单位方案名称已存在"))
        for field, value, message in checks:
            sql = select(self.model.id).where(
                getattr(self.model, field) == value,
            )
            if data_id:
                sql = sql.where(self.model.id != data_id)
            if (await self.db.scalar(sql)) is not None:
                raise CustomException(message)

    async def prepare_product_units(self, data: dict):
        if self.model.__tablename__ != "erp_product":
            return
        from . import models

        if data.get("multi_unit_enabled"):
            if not data.get("unit_group_id"):
                raise CustomException("启用多单位后必须选择多单位方案")
            group = await self.db.scalar(
                select(models.ErpUnitGroup).where(
                    models.ErpUnitGroup.id == data["unit_group_id"],
                    models.ErpUnitGroup.is_active == True,
                    models.ErpUnitGroup.is_delete == false(),
                )
            )
            if group is None:
                raise CustomException("多单位方案不存在或已停用")
            data["base_unit_id"] = group.primary_unit_id
        else:
            data["unit_group_id"] = None
            if not data.get("base_unit_id"):
                raise CustomException("单单位商品必须选择基本单位")
            unit_exists = await self.db.scalar(
                select(models.ErpUnit.id).where(
                    models.ErpUnit.id == data["base_unit_id"],
                    models.ErpUnit.is_active == True,
                    models.ErpUnit.is_delete == false(),
                )
            )
            if unit_exists is None:
                raise CustomException("基本单位不存在或已停用")

    async def ensure_unit_group(self, data: dict, data_id: int | None = None):
        if self.model.__tablename__ != "erp_unit_group":
            return
        from . import models

        unit_exists = await self.db.scalar(
            select(models.ErpUnit.id).where(
                models.ErpUnit.id == data["primary_unit_id"],
                models.ErpUnit.is_active == True,
                models.ErpUnit.is_delete == false(),
            )
        )
        if unit_exists is None:
            raise CustomException("主单位不存在或已停用")
        if data_id:
            item_exists = await self.db.scalar(
                select(models.ErpUnitGroupItem.id).where(
                    models.ErpUnitGroupItem.group_id == data_id,
                    models.ErpUnitGroupItem.unit_id == data["primary_unit_id"],
                    models.ErpUnitGroupItem.is_delete == false(),
                )
            )
            if item_exists is not None:
                raise CustomException("主单位不能同时作为该方案的子单位")

    async def sync_group_products(self, group_id: int, primary_unit_id: int):
        from . import models

        await self.db.execute(
            update(models.ErpProduct).where(
                models.ErpProduct.unit_group_id == group_id,
                models.ErpProduct.is_delete == false(),
            ).values(base_unit_id=primary_unit_id)
        )
        await self.db.flush()

    async def ensure_group_item(self, data: dict, data_id: int | None = None):
        from . import models

        group = await self.db.scalar(
            select(models.ErpUnitGroup).where(
                models.ErpUnitGroup.id == data["group_id"],
                models.ErpUnitGroup.is_delete == false(),
            )
        )
        if group is None:
            raise CustomException("多单位方案不存在")
        if group.primary_unit_id == data["unit_id"]:
            raise CustomException("子单位不能与主单位相同")
        unit_exists = await self.db.scalar(
            select(models.ErpUnit.id).where(
                models.ErpUnit.id == data["unit_id"],
                models.ErpUnit.is_active == True,
                models.ErpUnit.is_delete == false(),
            )
        )
        if unit_exists is None:
            raise CustomException("子单位不存在或已停用")
        duplicate = select(models.ErpUnitGroupItem.id).where(
            models.ErpUnitGroupItem.group_id == data["group_id"],
            models.ErpUnitGroupItem.unit_id == data["unit_id"],
            models.ErpUnitGroupItem.is_delete == false(),
        )
        if data_id:
            duplicate = duplicate.where(models.ErpUnitGroupItem.id != data_id)
        if (await self.db.scalar(duplicate)) is not None:
            raise CustomException("该单位已存在于当前多单位方案")
        parent_id = data.get("parent_id")
        if parent_id is None:
            return
        if parent_id == data_id:
            raise CustomException("上级单位不能选择自身")
        parent = await self.db.scalar(
            select(models.ErpUnitGroupItem).where(
                models.ErpUnitGroupItem.id == parent_id,
                models.ErpUnitGroupItem.group_id == data["group_id"],
                models.ErpUnitGroupItem.is_delete == false(),
            )
        )
        if parent is None:
            raise CustomException("所选上级单位不属于当前方案")
        visited = {data_id} if data_id else set()
        current = parent
        while current is not None:
            if current.id in visited:
                raise CustomException("单位层级不能形成循环")
            visited.add(current.id)
            if current.parent_id is None:
                break
            current = await self.db.scalar(
                select(models.ErpUnitGroupItem).where(
                    models.ErpUnitGroupItem.id == current.parent_id,
                    models.ErpUnitGroupItem.is_delete == false(),
                )
            )

    async def ensure_group_item_not_referenced(self, ids: list[int], group_id: int):
        from . import models

        item_count = await self.db.scalar(
            select(func.count(models.ErpUnitGroupItem.id)).where(
                models.ErpUnitGroupItem.id.in_(ids),
                models.ErpUnitGroupItem.group_id == group_id,
            )
        )
        if item_count != len(set(ids)):
            raise CustomException("包含不属于当前方案的单位明细")
        child = await self.db.scalar(
            select(models.ErpUnitGroupItem.id).where(
                models.ErpUnitGroupItem.parent_id.in_(ids),
                models.ErpUnitGroupItem.is_delete == false(),
            ).limit(1)
        )
        if child is not None:
            raise CustomException("该单位下存在子单位，不能删除")

    async def ensure_not_referenced(self, ids: list[int]):
        from . import models

        references = {
            "erp_product_category": [
                (models.ErpProductCategory, "parent_id", "分类下存在子分类，不能删除"),
                (models.ErpProductSpu, "category_id", "分类已被商品SPU使用，不能删除"),
                (models.ErpProduct, "category_id", "分类已被商品使用，不能删除"),
            ],
            "erp_unit": [
                (models.ErpProduct, "base_unit_id", "单位已被商品使用，不能删除"),
                (models.ErpUnitGroup, "primary_unit_id", "单位已被多单位方案设为主单位，不能删除"),
                (models.ErpUnitGroupItem, "unit_id", "单位已被多单位方案使用，不能删除"),
            ],
            "erp_unit_group": [
                (models.ErpProduct, "unit_group_id", "多单位方案已被商品使用，不能删除"),
            ],
            "erp_settlement_method": [
                (models.ErpCustomer, "settlement_method_id", "结算方式已被客户使用，不能删除"),
                (models.ErpSupplier, "settlement_method_id", "结算方式已被供应商使用，不能删除"),
            ],
        }
        for ref_model, field, message in references.get(self.model.__tablename__, []):
            sql = select(ref_model.id).where(
                getattr(ref_model, field).in_(ids), ref_model.is_delete == false()
            ).limit(1)
            if (await self.db.scalar(sql)) is not None:
                raise CustomException(message)

    async def ensure_category_parent(self, data_id: int, parent_id: int | None):
        if self.model.__tablename__ != "erp_product_category" or parent_id is None:
            return
        visited = {data_id}
        current_id = parent_id
        while current_id is not None:
            if current_id in visited:
                raise CustomException("上级分类不能形成循环层级")
            visited.add(current_id)
            current_id = await self.db.scalar(
                select(self.model.parent_id).where(
                    self.model.id == current_id, self.model.is_delete == false()
                )
            )
