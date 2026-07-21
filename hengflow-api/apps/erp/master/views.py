from dataclasses import dataclass
from typing import Type

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel

from apps.vadmin.auth.utils.current import AllUserAuth, FullAdminAuth
from apps.vadmin.auth.utils.validation.auth import Auth
from core.dependencies import IdList
from utils.response import SuccessResponse

from . import models, schemas
from .crud import MasterDal
from .services import ProductSpuService

app = APIRouter()


@app.get("/product-spus", summary="查询商品 SPU 和 SKU 汇总")
async def list_product_spus(
    keyword: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    limit: int = 10,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.master.product.list"])),
):
    """分页查询商品公共档案，并返回其 SKU 和库存汇总。"""

    data, count = await ProductSpuService(auth.db).list(page, limit, keyword, is_active)
    return SuccessResponse(data, count=count)


@app.get("/product-spus/attribute-options", summary="获取 SKU 属性和值")
async def get_product_attribute_options(auth: Auth = Depends(AllUserAuth())):
    """返回历史使用过的规格属性和值供前端自动补全。"""

    return SuccessResponse(await ProductSpuService(auth.db).attribute_options())


@app.get("/product-spus/{spu_id}", summary="获取商品 SPU 和全部 SKU")
async def get_product_spu(
    spu_id: int,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.master.product.view", "erp.master.product.update"])),
):
    """读取一个商品及其全部 SKU 明细。"""

    return SuccessResponse(await ProductSpuService(auth.db).detail(spu_id))


@app.post("/product-spus", summary="新增商品 SPU 和 SKU")
async def create_product_spu(
    data: schemas.ProductSpuInput,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.master.product.create"])),
):
    """在同一事务中创建 SPU、SKU 和规格属性。"""

    return SuccessResponse(await ProductSpuService(auth.db).save(data))


@app.put("/product-spus/{spu_id}", summary="修改商品 SPU 和 SKU")
async def update_product_spu(
    spu_id: int,
    data: schemas.ProductSpuInput,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.master.product.update"])),
):
    """同步修改 SPU 和其全部 SKU。"""

    return SuccessResponse(await ProductSpuService(auth.db).save(data, spu_id))


@app.delete("/product-spus/{spu_id}", summary="删除未使用商品 SPU")
async def delete_product_spu(
    spu_id: int,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.master.product.delete"])),
):
    """删除未被任何业务引用的 SPU 和 SKU。"""

    await ProductSpuService(auth.db).delete(spu_id)
    return SuccessResponse("删除成功")


@dataclass(frozen=True)
class Resource:
    model: type
    schema: Type[BaseModel]
    search_fields: tuple[str, ...]
    option_fields: tuple[str, ...] = ("code", "name")
    permission_key: str | None = None


RESOURCES = {
    "product-categories": Resource(models.ErpProductCategory, schemas.ProductCategory, ("code", "name")),
    "units": Resource(models.ErpUnit, schemas.Unit, ("code", "name", "symbol")),
    "unit-conversions": Resource(
        models.ErpUnitGroup, schemas.UnitGroup, ("name", "remark"), ("name",), "unit_conversion"
    ),
    "settlement-methods": Resource(models.ErpSettlementMethod, schemas.SettlementMethod, ("code", "name")),
    "warehouses": Resource(models.ErpWarehouse, schemas.Warehouse, ("code", "name", "manager_name")),
    "customers": Resource(models.ErpCustomer, schemas.Customer, ("code", "name", "short_name", "contact_name", "phone")),
    "suppliers": Resource(models.ErpSupplier, schemas.Supplier, ("code", "name", "short_name", "contact_name", "phone")),
    "employees": Resource(models.ErpEmployee, schemas.Employee, ("code", "name", "phone")),
}


def permission_name(resource: str) -> str:
    name = resource.replace("-", "_")
    return f"{name[:-3]}y" if name.endswith("ies") else name.removesuffix("s")


def register_resource(resource: str, config: Resource):
    permission = f"erp.master.{config.permission_key or permission_name(resource)}"

    async def list_data(
        keyword: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        limit: int = 10,
        auth: Auth = Depends(FullAdminAuth(permissions=[f"{permission}.list"])),
    ):
        datas, count = await MasterDal(auth.db, config.model).get_list(
            page, limit, keyword, is_active, config.search_fields
        )
        return SuccessResponse(datas, count=count)

    async def get_data(
        data_id: int,
        auth: Auth = Depends(FullAdminAuth(permissions=[f"{permission}.view", f"{permission}.update"])),
    ):
        data = await MasterDal(auth.db, config.model).get_data(data_id)
        return SuccessResponse(await MasterDal(auth.db, config.model).out_dict(data))

    async def create_data(
        data: dict = Body(...),
        auth: Auth = Depends(FullAdminAuth(permissions=[f"{permission}.create"])),
    ):
        values = config.schema.model_validate(data).model_dump()
        dal = MasterDal(auth.db, config.model)
        await dal.prepare_product_units(values)
        await dal.ensure_unit_group(values)
        await dal.ensure_unique(values)
        return SuccessResponse(await dal.create_data(values))

    async def update_data(
        data_id: int,
        data: dict = Body(...),
        auth: Auth = Depends(FullAdminAuth(permissions=[f"{permission}.update"])),
    ):
        values = config.schema.model_validate(data).model_dump()
        dal = MasterDal(auth.db, config.model)
        await dal.prepare_product_units(values)
        await dal.ensure_unit_group(values, data_id)
        await dal.ensure_category_parent(data_id, values.get("parent_id"))
        await dal.ensure_unique(values, data_id)
        result = await dal.put_data(data_id, values)
        if config.model is models.ErpUnitGroup:
            await dal.sync_group_products(data_id, values["primary_unit_id"])
        return SuccessResponse(result)

    async def delete_data(
        ids: IdList = Depends(),
        auth: Auth = Depends(FullAdminAuth(permissions=[f"{permission}.delete"])),
    ):
        dal = MasterDal(auth.db, config.model)
        await dal.ensure_not_referenced(ids.ids)
        # 多单位方案在确认未被商品引用后硬删除，并由数据库级联清理树形明细。
        await dal.delete_datas(ids.ids, v_soft=config.model is not models.ErpUnitGroup)
        return SuccessResponse("删除成功")

    app.add_api_route(f"/{resource}", list_data, methods=["GET"], summary=f"查询{resource}")
    app.add_api_route(f"/{resource}/{{data_id}}", get_data, methods=["GET"], summary=f"获取{resource}")
    app.add_api_route(f"/{resource}", create_data, methods=["POST"], summary=f"新增{resource}")
    app.add_api_route(f"/{resource}/{{data_id}}", update_data, methods=["PUT"], summary=f"修改{resource}")
    app.add_api_route(f"/{resource}", delete_data, methods=["DELETE"], summary=f"删除{resource}")


@app.get("/select-options/{resource}/all", summary="获取基础资料下拉选项")
async def get_options(resource: str, auth: Auth = Depends(AllUserAuth())):
    config = RESOURCES.get(resource)
    if not config:
        from core.exception import CustomException
        raise CustomException("不支持的基础资料类型")
    datas = await MasterDal(auth.db, config.model).get_datas(limit=0, is_active=True, v_order_field="id", v_return_objs=True)
    result = []
    for item in datas:
        if resource == "unit-conversions":
            label = item.name
        else:
            code = getattr(item, "code", "")
            name = getattr(item, "name", "")
            label = f"{code} - {name}" if code else name
        result.append({"value": item.id, "label": label})
    return SuccessResponse(result)


for resource_name, resource_config in RESOURCES.items():
    register_resource(resource_name, resource_config)


@app.get("/unit-conversions/{group_id}/items", summary="获取多单位方案明细")
async def get_unit_group_items(
    group_id: int,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.master.unit_conversion.list"])),
):
    dal = MasterDal(auth.db, models.ErpUnitGroupItem)
    datas = await dal.get_datas(
        limit=0, group_id=group_id, v_order_field="order", v_return_objs=False
    )
    return SuccessResponse(datas)


@app.post("/unit-conversions/{group_id}/items", summary="新增多单位方案明细")
async def create_unit_group_item(
    group_id: int,
    data: dict = Body(...),
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.master.unit_conversion.create"])),
):
    values = {**data, "group_id": group_id}
    values = schemas.UnitGroupItem.model_validate(values).model_dump()
    dal = MasterDal(auth.db, models.ErpUnitGroupItem)
    await dal.ensure_group_item(values)
    return SuccessResponse(await dal.create_data(values))


@app.put("/unit-conversions/{group_id}/items/{data_id}", summary="修改多单位方案明细")
async def update_unit_group_item(
    group_id: int,
    data_id: int,
    data: dict = Body(...),
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.master.unit_conversion.update"])),
):
    values = {**data, "group_id": group_id}
    values = schemas.UnitGroupItem.model_validate(values).model_dump()
    dal = MasterDal(auth.db, models.ErpUnitGroupItem)
    await dal.ensure_group_item(values, data_id)
    return SuccessResponse(await dal.put_data(data_id, values))


@app.delete("/unit-conversions/{group_id}/items", summary="删除多单位方案明细")
async def delete_unit_group_items(
    group_id: int,
    ids: IdList = Depends(),
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.master.unit_conversion.delete"])),
):
    dal = MasterDal(auth.db, models.ErpUnitGroupItem)
    await dal.ensure_group_item_not_referenced(ids.ids, group_id)
    await dal.delete_datas(ids.ids, v_soft=False)
    return SuccessResponse("删除成功")
