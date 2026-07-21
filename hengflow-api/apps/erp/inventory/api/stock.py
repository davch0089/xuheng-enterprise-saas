"""库存查询 HTTP 接口。"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends

from apps.vadmin.auth.utils.current import FullAdminAuth
from apps.vadmin.auth.utils.validation.auth import Auth
from utils.response import SuccessResponse

from .dependencies import query_service


router = APIRouter()


@router.get("/stocks", summary="查询库存余额")
async def list_stocks(
    page: int = 1,
    limit: int = 20,
    keyword: str | None = None,
    warehouse_id: int | None = None,
    category_id: int | None = None,
    stock_status: str | None = None,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.inventory.stock.list"])),
):
    """分页返回库存余额和库存价值汇总。"""

    data, count = await query_service(auth).balances(
        page, limit, keyword, warehouse_id, category_id, stock_status
    )
    return SuccessResponse(data, count=count)


@router.get("/batch-allocation", summary="批次FIFO推荐")
async def batch_allocation(
    warehouse_id: int,
    product_id: int,
    quantity: Decimal,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.inventory.stock.list"])),
):
    """返回批次先进先出和临期优先建议。"""

    return SuccessResponse(await query_service(auth).fifo_batches(warehouse_id, product_id, quantity))


@router.get("/stock-serials/{serial_id}/history", summary="序列号生命周期")
async def serial_history(
    serial_id: int,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.inventory.stock.list"])),
):
    """返回序列号每次状态和仓库变化。"""

    return SuccessResponse(await query_service(auth).serial_history(serial_id))


@router.get("/stock-movements", summary="查询库存收发明细")
async def list_stock_movements(
    page: int = 1,
    limit: int = 20,
    keyword: str | None = None,
    warehouse_id: int | None = None,
    product_id: int | None = None,
    direction: int | None = None,
    date_start: date | None = None,
    date_end: date | None = None,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.inventory.stock.list"])),
):
    """分页返回库存收发流水。"""

    data, count = await query_service(auth).movements(
        page, limit, keyword, warehouse_id, product_id, direction, date_start, date_end
    )
    return SuccessResponse(data, count=count)


@router.get("/stock-batches", summary="查询批次库存")
async def list_stock_batches(
    page: int = 1,
    limit: int = 20,
    keyword: str | None = None,
    warehouse_id: int | None = None,
    expiry_status: str | None = None,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.inventory.stock.list"])),
):
    """分页返回批次库存和有效期信息。"""

    data, count = await query_service(auth).batches(page, limit, keyword, warehouse_id, expiry_status)
    return SuccessResponse(data, count=count)


@router.get("/stock-serials", summary="查询序列号库存")
async def list_stock_serials(
    page: int = 1,
    limit: int = 20,
    keyword: str | None = None,
    warehouse_id: int | None = None,
    status: str | None = None,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.inventory.stock.list"])),
):
    """分页返回序列号库存状态。"""

    data, count = await query_service(auth).serials(page, limit, keyword, warehouse_id, status)
    return SuccessResponse(data, count=count)
