"""销售基础选择项和来源单据接口。"""

from fastapi import APIRouter, Depends

from apps.vadmin.auth.utils.current import AllUserAuth
from apps.vadmin.auth.utils.validation.auth import Auth
from utils.response import SuccessResponse

from .dependencies import query_service


router = APIRouter()


@router.get("/options", summary="销售业务选择项")
async def options(auth: Auth = Depends(AllUserAuth())):
    """返回销售业务基础资料选择项。"""

    return SuccessResponse(await query_service(auth).options())


@router.get("/products", summary="搜索销售商品")
async def products(
    keyword: str | None = None,
    warehouse_id: int | None = None,
    limit: int = 30,
    auth: Auth = Depends(AllUserAuth()),
):
    """搜索商品并返回售价、可用库存和多单位。"""

    return SuccessResponse(await query_service(auth).products(keyword, warehouse_id, limit))


@router.get("/source-orders", summary="可出库销售订单")
async def source_orders(
    customer_id: int | None = None, auth: Auth = Depends(AllUserAuth())
):
    """返回仍有未交数量的销售订单。"""

    return SuccessResponse(await query_service(auth).source_orders(customer_id))


@router.get("/source-deliveries", summary="可退货销售出库")
async def source_deliveries(
    customer_id: int | None = None, auth: Auth = Depends(AllUserAuth())
):
    """返回仍有可退数量的销售出库单。"""

    return SuccessResponse(await query_service(auth).source_deliveries(customer_id))
