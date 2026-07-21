"""销售订单、出库和退货 HTTP 接口。"""

from datetime import date

from fastapi import APIRouter, Depends

from apps.vadmin.auth.utils.current import FullAdminAuth
from apps.vadmin.auth.utils.validation.auth import Auth
from core.dependencies import IdList
from utils.response import SuccessResponse

from .. import schemas
from .dependencies import delivery_service, order_service, query_service, return_service


router = APIRouter()


def permission(document: str, action: str):
    """构造销售单据权限依赖。"""

    return FullAdminAuth(permissions=[f"erp.sales.{document}.{action}"])


@router.get("/orders", summary="销售订单列表")
async def order_list(
    page: int = 1,
    limit: int = 20,
    keyword: str | None = None,
    status: str | None = None,
    customer_id: int | None = None,
    date_start: date | None = None,
    date_end: date | None = None,
    auth: Auth = Depends(permission("order", "list")),
):
    """分页查询销售订单。"""

    data, count = await query_service(auth).document_list(
        "order", page, limit, keyword, status, customer_id, date_start, date_end
    )
    return SuccessResponse(data, count=count)


@router.get("/orders/{document_id}", summary="销售订单详情")
async def order_detail(
    document_id: int, auth: Auth = Depends(permission("order", "view"))
):
    """返回销售订单详情。"""

    return SuccessResponse(await order_service(auth).detail(document_id))


@router.post("/orders", summary="新增销售订单")
async def order_create(
    data: schemas.SalesOrderInput, auth: Auth = Depends(permission("order", "create"))
):
    """新增草稿销售订单。"""

    return SuccessResponse(await order_service(auth).save(data))


@router.put("/orders/{document_id}", summary="修改销售订单")
async def order_update(
    document_id: int,
    data: schemas.SalesOrderInput,
    auth: Auth = Depends(permission("order", "update")),
):
    """修改草稿销售订单。"""

    return SuccessResponse(await order_service(auth).save(data, document_id))


@router.delete("/orders", summary="删除销售订单")
async def order_delete(
    ids: IdList = Depends(), auth: Auth = Depends(permission("order", "delete"))
):
    """删除草稿销售订单。"""

    await order_service(auth).delete(ids.ids)
    return SuccessResponse("删除成功")


@router.post("/orders/{document_id}/approve", summary="审核销售订单")
async def order_approve(
    document_id: int, auth: Auth = Depends(permission("order", "approve"))
):
    """审核订单并预留库存。"""

    return SuccessResponse(await order_service(auth).approve(document_id))


@router.post("/orders/{document_id}/unapprove", summary="反审核销售订单")
async def order_unapprove(
    document_id: int, auth: Auth = Depends(permission("order", "unapprove"))
):
    """反审核订单并释放预留。"""

    return SuccessResponse(await order_service(auth).unapprove(document_id))


@router.get("/deliveries", summary="销售出库列表")
async def delivery_list(
    page: int = 1,
    limit: int = 20,
    keyword: str | None = None,
    status: str | None = None,
    customer_id: int | None = None,
    auth: Auth = Depends(permission("delivery", "list")),
):
    """分页查询销售出库单。"""

    data, count = await query_service(auth).document_list(
        "delivery", page, limit, keyword, status, customer_id
    )
    return SuccessResponse(data, count=count)


@router.get("/deliveries/{document_id}", summary="销售出库详情")
async def delivery_detail(
    document_id: int, auth: Auth = Depends(permission("delivery", "view"))
):
    """返回销售出库详情。"""

    return SuccessResponse(await delivery_service(auth).detail(document_id))


@router.post("/deliveries", summary="新增销售出库")
async def delivery_create(
    data: schemas.SalesDeliveryInput,
    auth: Auth = Depends(permission("delivery", "create")),
):
    """新增草稿销售出库单。"""

    return SuccessResponse(await delivery_service(auth).save(data))


@router.put("/deliveries/{document_id}", summary="修改销售出库")
async def delivery_update(
    document_id: int,
    data: schemas.SalesDeliveryInput,
    auth: Auth = Depends(permission("delivery", "update")),
):
    """修改草稿销售出库单。"""

    return SuccessResponse(await delivery_service(auth).save(data, document_id))


@router.delete("/deliveries", summary="删除销售出库")
async def delivery_delete(
    ids: IdList = Depends(), auth: Auth = Depends(permission("delivery", "delete"))
):
    """删除草稿销售出库单。"""

    await delivery_service(auth).delete(ids.ids)
    return SuccessResponse("删除成功")


@router.post("/deliveries/{document_id}/approve", summary="审核销售出库")
async def delivery_approve(
    document_id: int, auth: Auth = Depends(permission("delivery", "approve"))
):
    """审核出库并联动库存成本和应收。"""

    return SuccessResponse(await delivery_service(auth).approve(document_id))


@router.post("/deliveries/{document_id}/unapprove", summary="反审核销售出库")
async def delivery_unapprove(
    document_id: int, auth: Auth = Depends(permission("delivery", "unapprove"))
):
    """反审核并冲销库存成本和应收。"""

    return SuccessResponse(await delivery_service(auth).unapprove(document_id))


@router.get("/returns", summary="销售退货列表")
async def return_list(
    page: int = 1,
    limit: int = 20,
    keyword: str | None = None,
    status: str | None = None,
    customer_id: int | None = None,
    auth: Auth = Depends(permission("return", "list")),
):
    """分页查询销售退货单。"""

    data, count = await query_service(auth).document_list(
        "return", page, limit, keyword, status, customer_id
    )
    return SuccessResponse(data, count=count)


@router.get("/returns/{document_id}", summary="销售退货详情")
async def return_detail(
    document_id: int, auth: Auth = Depends(permission("return", "view"))
):
    """返回销售退货详情。"""

    return SuccessResponse(await return_service(auth).detail(document_id))


@router.post("/returns", summary="新增销售退货")
async def return_create(
    data: schemas.SalesReturnInput,
    auth: Auth = Depends(permission("return", "create")),
):
    """新增草稿销售退货单。"""

    return SuccessResponse(await return_service(auth).save(data))


@router.put("/returns/{document_id}", summary="修改销售退货")
async def return_update(
    document_id: int,
    data: schemas.SalesReturnInput,
    auth: Auth = Depends(permission("return", "update")),
):
    """修改草稿销售退货单。"""

    return SuccessResponse(await return_service(auth).save(data, document_id))


@router.delete("/returns", summary="删除销售退货")
async def return_delete(
    ids: IdList = Depends(), auth: Auth = Depends(permission("return", "delete"))
):
    """删除草稿销售退货单。"""

    await return_service(auth).delete(ids.ids)
    return SuccessResponse("删除成功")


@router.post("/returns/{document_id}/approve", summary="审核销售退货")
async def return_approve(
    document_id: int, auth: Auth = Depends(permission("return", "approve"))
):
    """审核退货并联动回库和红字应收。"""

    return SuccessResponse(await return_service(auth).approve(document_id))


@router.post("/returns/{document_id}/unapprove", summary="反审核销售退货")
async def return_unapprove(
    document_id: int, auth: Auth = Depends(permission("return", "unapprove"))
):
    """反审核并冲销退货库存和应收。"""

    return SuccessResponse(await return_service(auth).unapprove(document_id))
