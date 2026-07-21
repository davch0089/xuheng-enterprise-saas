"""BOM及组装拆卸HTTP接口。"""

from fastapi import APIRouter, Depends

from apps.vadmin.auth.utils.current import FullAdminAuth
from apps.vadmin.auth.utils.validation.auth import Auth
from core.dependencies import IdList
from utils.response import SuccessResponse

from .. import assembly_schemas as schemas
from .dependencies import assembly_service, bom_service


router = APIRouter()


def permission(domain: str, action: str):
    """构造BOM和工单权限依赖。"""

    return FullAdminAuth(permissions=[f"erp.inventory.{domain}.{action}"])


@router.get("/boms")
async def bom_list(page: int = 1, limit: int = 20, keyword: str | None = None, is_active: bool | None = None, auth: Auth = Depends(permission("bom", "list"))):
    """分页查询BOM。"""

    data, count = await bom_service(auth).list(page, limit, keyword, is_active)
    return SuccessResponse(data, count=count)


@router.get("/boms/{document_id}")
async def bom_detail(document_id: int, auth: Auth = Depends(permission("bom", "view"))):
    """返回BOM详情。"""

    return SuccessResponse(await bom_service(auth).detail(document_id))


@router.post("/boms")
async def bom_create(data: schemas.BomInput, auth: Auth = Depends(permission("bom", "create"))):
    """新增BOM。"""

    return SuccessResponse(await bom_service(auth).save(data))


@router.put("/boms/{document_id}")
async def bom_update(document_id: int, data: schemas.BomInput, auth: Auth = Depends(permission("bom", "update"))):
    """修改BOM。"""

    return SuccessResponse(await bom_service(auth).save(data, document_id))


@router.delete("/boms")
async def bom_delete(ids: IdList = Depends(), auth: Auth = Depends(permission("bom", "delete"))):
    """删除未引用BOM。"""

    await bom_service(auth).delete(ids.ids)
    return SuccessResponse("删除成功")


@router.get("/assembly-orders")
async def order_list(page: int = 1, limit: int = 20, keyword: str | None = None, status: str | None = None, auth: Auth = Depends(permission("assembly", "list"))):
    """分页查询组装拆卸工单。"""

    data, count = await assembly_service(auth).list(page, limit, status, keyword)
    return SuccessResponse(data, count=count)


@router.get("/assembly-orders/{document_id}")
async def order_detail(document_id: int, auth: Auth = Depends(permission("assembly", "view"))):
    """返回组装拆卸工单详情。"""

    return SuccessResponse(await assembly_service(auth).detail(document_id))


@router.post("/assembly-orders")
async def order_create(data: schemas.AssemblyOrderInput, auth: Auth = Depends(permission("assembly", "create"))):
    """新增组装拆卸工单。"""

    return SuccessResponse(await assembly_service(auth).save(data))


@router.put("/assembly-orders/{document_id}")
async def order_update(document_id: int, data: schemas.AssemblyOrderInput, auth: Auth = Depends(permission("assembly", "update"))):
    """修改组装拆卸工单。"""

    return SuccessResponse(await assembly_service(auth).save(data, document_id))


@router.delete("/assembly-orders")
async def order_delete(ids: IdList = Depends(), auth: Auth = Depends(permission("assembly", "delete"))):
    """删除工单草稿。"""

    await assembly_service(auth).delete(ids.ids)
    return SuccessResponse("删除成功")


@router.post("/assembly-orders/{document_id}/approve")
async def order_approve(document_id: int, auth: Auth = Depends(permission("assembly", "approve"))):
    """审核工单并归集成本。"""

    return SuccessResponse(await assembly_service(auth).approve(document_id))


@router.post("/assembly-orders/{document_id}/unapprove")
async def order_unapprove(document_id: int, auth: Auth = Depends(permission("assembly", "unapprove"))):
    """反审核工单并冲销库存成本。"""

    return SuccessResponse(await assembly_service(auth).unapprove(document_id))
