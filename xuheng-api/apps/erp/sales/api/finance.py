"""销售应收和收款 HTTP 接口。"""

from fastapi import APIRouter, Depends

from apps.vadmin.auth.utils.current import FullAdminAuth
from apps.vadmin.auth.utils.validation.auth import Auth
from core.dependencies import IdList
from utils.response import SuccessResponse

from .. import schemas
from .dependencies import query_service, receipt_service


router = APIRouter()


@router.get("/receivables", summary="客户应收列表")
async def receivable_list(
    page: int = 1,
    limit: int = 20,
    customer_id: int | None = None,
    status: str | None = None,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.sales.receivable.list"])),
):
    """分页查询客户应收开放项目。"""

    data, count = await query_service(auth).receivables(
        page, limit, customer_id, status
    )
    return SuccessResponse(data, count=count)


@router.get("/receipts", summary="销售收款列表")
async def receipt_list(
    page: int = 1,
    limit: int = 20,
    customer_id: int | None = None,
    status: str | None = None,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.sales.receipt.list"])),
):
    """分页查询销售收款单。"""

    data, count = await query_service(auth).receipt_list(
        page, limit, customer_id, status
    )
    return SuccessResponse(data, count=count)


@router.get("/receipts/{receipt_id}", summary="销售收款详情")
async def receipt_detail(
    receipt_id: int,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.sales.receipt.view"])),
):
    """返回销售收款详情。"""

    return SuccessResponse(await receipt_service(auth).detail(receipt_id))


@router.post("/receipts", summary="新增销售收款")
async def receipt_create(
    data: schemas.SalesReceiptInput,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.sales.receipt.create"])),
):
    """新增草稿销售收款单。"""

    return SuccessResponse(await receipt_service(auth).save(data))


@router.put("/receipts/{receipt_id}", summary="修改销售收款")
async def receipt_update(
    receipt_id: int,
    data: schemas.SalesReceiptInput,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.sales.receipt.update"])),
):
    """修改草稿销售收款单。"""

    return SuccessResponse(await receipt_service(auth).save(data, receipt_id))


@router.delete("/receipts", summary="删除销售收款")
async def receipt_delete(
    ids: IdList = Depends(),
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.sales.receipt.delete"])),
):
    """删除草稿销售收款单。"""

    await receipt_service(auth).delete(ids.ids)
    return SuccessResponse("删除成功")


@router.post("/receipts/{receipt_id}/approve", summary="审核销售收款")
async def receipt_approve(
    receipt_id: int,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.sales.receipt.approve"])),
):
    """审核收款并核销应收。"""

    return SuccessResponse(await receipt_service(auth).approve(receipt_id))


@router.post("/receipts/{receipt_id}/unapprove", summary="反审核销售收款")
async def receipt_unapprove(
    receipt_id: int,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.sales.receipt.unapprove"])),
):
    """反审核收款并撤销核销。"""

    return SuccessResponse(await receipt_service(auth).unapprove(receipt_id))
