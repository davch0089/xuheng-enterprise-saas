"""入库单 HTTP 接口。"""

from datetime import date

from fastapi import APIRouter, Depends

from apps.vadmin.auth.utils.current import AllUserAuth, FullAdminAuth
from apps.vadmin.auth.utils.validation.auth import Auth
from core.dependencies import IdList
from utils.response import SuccessResponse

from ..schemas import InboundReceiptInput
from .dependencies import service


router = APIRouter()


@router.get("/products", summary="搜索可入库商品")
async def search_products(
    keyword: str | None = None,
    warehouse_id: int | None = None,
    limit: int = 30,
    auth: Auth = Depends(AllUserAuth()),
):
    """搜索可用于入库录入的商品和单位信息。"""

    return SuccessResponse(await service(auth).search_products(keyword, warehouse_id, limit))


@router.get("/inbounds", summary="查询入库单")
async def list_inbounds(
    page: int = 1,
    limit: int = 10,
    keyword: str | None = None,
    status: str | None = None,
    business_type: str | None = None,
    date_start: date | None = None,
    date_end: date | None = None,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.inventory.inbound.list"])),
):
    """分页返回符合筛选条件的入库单。"""

    data, count = await service(auth).receipt_list(
        page, limit, keyword, status, business_type, date_start, date_end
    )
    return SuccessResponse(data, count=count)


@router.get("/inbounds/{receipt_id}", summary="获取入库单")
async def get_inbound(
    receipt_id: int,
    auth: Auth = Depends(
        FullAdminAuth(permissions=["erp.inventory.inbound.view", "erp.inventory.inbound.update"])
    ),
):
    """返回指定入库单的完整详情。"""

    return SuccessResponse(await service(auth).receipt_detail(receipt_id))


@router.post("/inbounds", summary="新增入库单")
async def create_inbound(
    data: InboundReceiptInput,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.inventory.inbound.create"])),
):
    """创建一张草稿入库单。"""

    return SuccessResponse(await service(auth).save_receipt(data))


@router.put("/inbounds/{receipt_id}", summary="修改入库单")
async def update_inbound(
    receipt_id: int,
    data: InboundReceiptInput,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.inventory.inbound.update"])),
):
    """更新一张草稿入库单。"""

    return SuccessResponse(await service(auth).save_receipt(data, receipt_id))


@router.delete("/inbounds", summary="删除入库单")
async def delete_inbound(
    ids: IdList = Depends(),
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.inventory.inbound.delete"])),
):
    """批量删除草稿入库单。"""

    await service(auth).delete_receipts(ids.ids)
    return SuccessResponse("删除成功")


@router.post("/inbounds/{receipt_id}/approve", summary="审核入库单")
async def approve_inbound(
    receipt_id: int,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.inventory.inbound.approve"])),
):
    """审核入库单并触发库存过账。"""

    return SuccessResponse(await service(auth).approve(receipt_id))


@router.post("/inbounds/{receipt_id}/unapprove", summary="反审核入库单")
async def unapprove_inbound(
    receipt_id: int,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.inventory.inbound.unapprove"])),
):
    """反审核入库单并冲销库存过账。"""

    return SuccessResponse(await service(auth).unapprove(receipt_id))
