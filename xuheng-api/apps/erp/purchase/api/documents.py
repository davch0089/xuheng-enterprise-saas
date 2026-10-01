"""采购订单、收货与退货 HTTP 接口。"""

from fastapi import APIRouter, Depends
from apps.vadmin.auth.utils.current import FullAdminAuth
from apps.vadmin.auth.utils.validation.auth import Auth
from core.dependencies import IdList
from utils.response import SuccessResponse
from .. import models, schemas
from .dependencies import order_service, receipt_service, return_service


router = APIRouter()


def permission(domain, action):
    """构造采购单据按钮权限。"""

    return FullAdminAuth(permissions=[f"erp.purchase.{domain}.{action}"])


@router.get("/orders")
async def orders(page: int = 1, limit: int = 20, status: str | None = None, keyword: str | None = None, supplier_id: int | None = None, auth: Auth = Depends(permission("order", "list"))):
    """分页查询采购订单。"""

    data, count = await order_service(auth).list(page, limit, status, keyword, supplier_id)
    return SuccessResponse(data, count=count)


@router.get("/orders/{document_id}")
async def order_detail(document_id: int, auth: Auth = Depends(permission("order", "view"))):
    """返回采购订单详情。"""

    return SuccessResponse(await order_service(auth).detail(models.ErpPurchaseOrder, models.ErpPurchaseOrderLine, "order_id", document_id))


@router.post("/orders")
async def order_create(data: schemas.PurchaseOrderInput, auth: Auth = Depends(permission("order", "create"))):
    """新增采购订单。"""

    return SuccessResponse(await order_service(auth).save(data))


@router.put("/orders/{document_id}")
async def order_update(document_id: int, data: schemas.PurchaseOrderInput, auth: Auth = Depends(permission("order", "update"))):
    """修改采购订单。"""

    return SuccessResponse(await order_service(auth).save(data, document_id))


@router.delete("/orders")
async def order_delete(ids: IdList = Depends(), auth: Auth = Depends(permission("order", "delete"))):
    """删除采购订单草稿。"""

    await order_service(auth).delete(ids.ids)
    return SuccessResponse("删除成功")


@router.post("/orders/{document_id}/approve")
async def order_approve(document_id: int, auth: Auth = Depends(permission("order", "approve"))):
    """审核采购订单。"""

    return SuccessResponse(await order_service(auth).approve(document_id))


@router.post("/orders/{document_id}/unapprove")
async def order_unapprove(document_id: int, auth: Auth = Depends(permission("order", "unapprove"))):
    """反审核采购订单。"""

    return SuccessResponse(await order_service(auth).unapprove(document_id))


@router.get("/receipts")
async def receipts(page: int = 1, limit: int = 20, status: str | None = None, keyword: str | None = None, supplier_id: int | None = None, auth: Auth = Depends(permission("receipt", "list"))):
    """分页查询采购收货单。"""

    data, count = await receipt_service(auth).list(page, limit, status, keyword, supplier_id)
    return SuccessResponse(data, count=count)


@router.get("/receipts/{document_id}")
async def receipt_detail(document_id: int, auth: Auth = Depends(permission("receipt", "view"))):
    """返回采购收货详情。"""

    return SuccessResponse(await receipt_service(auth).detail(models.ErpPurchaseReceipt, models.ErpPurchaseReceiptLine, "receipt_id", document_id))


@router.post("/receipts")
async def receipt_create(data: schemas.PurchaseReceiptInput, auth: Auth = Depends(permission("receipt", "create"))):
    """新增采购收货单。"""

    return SuccessResponse(await receipt_service(auth).save(data))


@router.put("/receipts/{document_id}")
async def receipt_update(document_id: int, data: schemas.PurchaseReceiptInput, auth: Auth = Depends(permission("receipt", "update"))):
    """修改采购收货单。"""

    return SuccessResponse(await receipt_service(auth).save(data, document_id))


@router.delete("/receipts")
async def receipt_delete(ids: IdList = Depends(), auth: Auth = Depends(permission("receipt", "delete"))):
    """删除采购收货草稿。"""

    await receipt_service(auth).delete(ids.ids)
    return SuccessResponse("删除成功")


@router.post("/receipts/{document_id}/approve")
async def receipt_approve(document_id: int, auth: Auth = Depends(permission("receipt", "approve"))):
    """审核采购收货。"""

    return SuccessResponse(await receipt_service(auth).approve(document_id))


@router.post("/receipts/{document_id}/unapprove")
async def receipt_unapprove(document_id: int, auth: Auth = Depends(permission("receipt", "unapprove"))):
    """反审核采购收货。"""

    return SuccessResponse(await receipt_service(auth).unapprove(document_id))


@router.get("/returns")
async def returns(page: int = 1, limit: int = 20, status: str | None = None, keyword: str | None = None, supplier_id: int | None = None, auth: Auth = Depends(permission("return", "list"))):
    """分页查询采购退货单。"""

    data, count = await return_service(auth).list(page, limit, status, keyword, supplier_id)
    return SuccessResponse(data, count=count)


@router.get("/returns/{document_id}")
async def return_detail(document_id: int, auth: Auth = Depends(permission("return", "view"))):
    """返回采购退货详情。"""

    return SuccessResponse(await return_service(auth).detail(models.ErpPurchaseReturn, models.ErpPurchaseReturnLine, "return_id", document_id))


@router.post("/returns")
async def return_create(data: schemas.PurchaseReturnInput, auth: Auth = Depends(permission("return", "create"))):
    """新增采购退货单。"""

    return SuccessResponse(await return_service(auth).save(data))


@router.put("/returns/{document_id}")
async def return_update(document_id: int, data: schemas.PurchaseReturnInput, auth: Auth = Depends(permission("return", "update"))):
    """修改采购退货单。"""

    return SuccessResponse(await return_service(auth).save(data, document_id))


@router.delete("/returns")
async def return_delete(ids: IdList = Depends(), auth: Auth = Depends(permission("return", "delete"))):
    """删除采购退货草稿。"""

    await return_service(auth).delete(ids.ids)
    return SuccessResponse("删除成功")


@router.post("/returns/{document_id}/approve")
async def return_approve(document_id: int, auth: Auth = Depends(permission("return", "approve"))):
    """审核采购退货。"""

    return SuccessResponse(await return_service(auth).approve(document_id))


@router.post("/returns/{document_id}/unapprove")
async def return_unapprove(document_id: int, auth: Auth = Depends(permission("return", "unapprove"))):
    """反审核采购退货。"""

    return SuccessResponse(await return_service(auth).unapprove(document_id))
