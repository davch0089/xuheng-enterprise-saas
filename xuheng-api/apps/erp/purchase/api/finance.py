"""供应商应付和采购付款 HTTP 接口。"""

from fastapi import APIRouter, Depends
from apps.vadmin.auth.utils.current import FullAdminAuth
from apps.vadmin.auth.utils.validation.auth import Auth
from core.dependencies import IdList
from utils.response import SuccessResponse
from .. import schemas
from .dependencies import payment_service, query_service


router = APIRouter()


def permission(action):
    """构造采购应付付款权限。"""

    return FullAdminAuth(permissions=[f"erp.purchase.payable.{action}"])


@router.get("/payables")
async def payables(page: int = 1, limit: int = 20, supplier_id: int | None = None, status: str | None = None, auth: Auth = Depends(permission("list"))):
    """分页查询供应商应付开放项目。"""

    data, count = await query_service(auth).payables(page, limit, supplier_id, status)
    return SuccessResponse(data, count=count)


@router.get("/payments")
async def payments(page: int = 1, limit: int = 20, supplier_id: int | None = None, status: str | None = None, auth: Auth = Depends(permission("list"))):
    """分页查询采购付款单。"""

    data, count = await query_service(auth).payments(page, limit, supplier_id, status)
    return SuccessResponse(data, count=count)


@router.get("/payments/{document_id}")
async def payment_detail(document_id: int, auth: Auth = Depends(permission("view"))):
    """返回采购付款详情。"""

    return SuccessResponse(await payment_service(auth).detail(document_id))


@router.post("/payments")
async def payment_create(data: schemas.PurchasePaymentInput, auth: Auth = Depends(permission("create"))):
    """新增采购付款单。"""

    return SuccessResponse(await payment_service(auth).save(data))


@router.put("/payments/{document_id}")
async def payment_update(document_id: int, data: schemas.PurchasePaymentInput, auth: Auth = Depends(permission("update"))):
    """修改采购付款单。"""

    return SuccessResponse(await payment_service(auth).save(data, document_id))


@router.delete("/payments")
async def payment_delete(ids: IdList = Depends(), auth: Auth = Depends(permission("delete"))):
    """删除采购付款草稿。"""

    await payment_service(auth).delete(ids.ids)
    return SuccessResponse("删除成功")


@router.post("/payments/{document_id}/approve")
async def payment_approve(document_id: int, auth: Auth = Depends(permission("approve"))):
    """审核采购付款。"""

    return SuccessResponse(await payment_service(auth).approve(document_id))


@router.post("/payments/{document_id}/unapprove")
async def payment_unapprove(document_id: int, auth: Auth = Depends(permission("unapprove"))):
    """反审核采购付款。"""

    return SuccessResponse(await payment_service(auth).unapprove(document_id))

