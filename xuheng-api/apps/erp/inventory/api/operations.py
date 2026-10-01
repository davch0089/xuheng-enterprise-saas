"""调拨、盘点和其他出入库 HTTP 接口。"""

from fastapi import APIRouter, Depends

from apps.vadmin.auth.utils.current import FullAdminAuth
from apps.vadmin.auth.utils.validation.auth import Auth
from core.dependencies import IdList
from utils.response import SuccessResponse

from .. import operation_schemas as schemas
from .dependencies import count_service, other_service, transfer_service


router = APIRouter()


def auth_permission(domain: str, action: str):
    """构造库存作业按钮权限依赖。"""

    return FullAdminAuth(permissions=[f"erp.inventory.{domain}.{action}"])


@router.get("/transfers", summary="库存调拨列表")
async def transfer_list(page: int = 1, limit: int = 20, status: str | None = None, keyword: str | None = None, auth: Auth = Depends(auth_permission("transfer", "list"))):
    """分页查询一步和两步调拨单。"""

    data, count = await transfer_service(auth).list(page, limit, status, keyword)
    return SuccessResponse(data, count=count)


@router.get("/transfers/{document_id}", summary="库存调拨详情")
async def transfer_detail(document_id: int, auth: Auth = Depends(auth_permission("transfer", "view"))):
    """返回库存调拨详情。"""

    return SuccessResponse(await transfer_service(auth).detail(document_id))


@router.post("/transfers", summary="新增库存调拨")
async def transfer_create(data: schemas.StockTransferInput, auth: Auth = Depends(auth_permission("transfer", "create"))):
    """新增调拨草稿。"""

    return SuccessResponse(await transfer_service(auth).save(data))


@router.put("/transfers/{document_id}", summary="修改库存调拨")
async def transfer_update(document_id: int, data: schemas.StockTransferInput, auth: Auth = Depends(auth_permission("transfer", "update"))):
    """修改调拨草稿。"""

    return SuccessResponse(await transfer_service(auth).save(data, document_id))


@router.delete("/transfers", summary="删除库存调拨")
async def transfer_delete(ids: IdList = Depends(), auth: Auth = Depends(auth_permission("transfer", "delete"))):
    """删除调拨草稿。"""

    await transfer_service(auth).delete(ids.ids)
    return SuccessResponse("删除成功")


@router.post("/transfers/{document_id}/dispatch", summary="调拨发运")
async def transfer_dispatch(document_id: int, auth: Auth = Depends(auth_permission("transfer", "dispatch"))):
    """执行调出；一步调拨同时执行调入。"""

    return SuccessResponse(await transfer_service(auth).dispatch(document_id))


@router.post("/transfers/{document_id}/receive", summary="调拨收货")
async def transfer_receive(document_id: int, auth: Auth = Depends(auth_permission("transfer", "receive"))):
    """确认两步调拨收货。"""

    return SuccessResponse(await transfer_service(auth).receive(document_id))


@router.post("/transfers/{document_id}/unreceive", summary="撤销调拨收货")
async def transfer_unreceive(document_id: int, auth: Auth = Depends(auth_permission("transfer", "unreceive"))):
    """冲销目标仓调拨入库。"""

    return SuccessResponse(await transfer_service(auth).unreceive(document_id))


@router.post("/transfers/{document_id}/undispatch", summary="撤销调拨发运")
async def transfer_undispatch(document_id: int, auth: Auth = Depends(auth_permission("transfer", "undispatch"))):
    """冲销源仓调拨出库。"""

    return SuccessResponse(await transfer_service(auth).undispatch(document_id))


@router.get("/count-snapshot", summary="仓库盘点快照")
async def count_snapshot(warehouse_id: int, auth: Auth = Depends(auth_permission("count", "create"))):
    """返回指定仓库的可盘点库存快照。"""

    return SuccessResponse(await count_service(auth).snapshot(warehouse_id))


@router.get("/counts", summary="库存盘点列表")
async def count_list(page: int = 1, limit: int = 20, status: str | None = None, keyword: str | None = None, auth: Auth = Depends(auth_permission("count", "list"))):
    """分页查询盘点单。"""

    data, count = await count_service(auth).list(page, limit, status, keyword)
    return SuccessResponse(data, count=count)


@router.get("/counts/{document_id}", summary="库存盘点详情")
async def count_detail(document_id: int, auth: Auth = Depends(auth_permission("count", "view"))):
    """返回盘点详情和差异。"""

    return SuccessResponse(await count_service(auth).detail(document_id))


@router.post("/counts", summary="新增库存盘点")
async def count_create(data: schemas.InventoryCountInput, auth: Auth = Depends(auth_permission("count", "create"))):
    """新增盘点草稿并锁定快照。"""

    return SuccessResponse(await count_service(auth).save(data))


@router.put("/counts/{document_id}", summary="修改库存盘点")
async def count_update(document_id: int, data: schemas.InventoryCountInput, auth: Auth = Depends(auth_permission("count", "update"))):
    """修改实盘结果并重取快照。"""

    return SuccessResponse(await count_service(auth).save(data, document_id))


@router.delete("/counts", summary="删除库存盘点")
async def count_delete(ids: IdList = Depends(), auth: Auth = Depends(auth_permission("count", "delete"))):
    """删除盘点草稿。"""

    await count_service(auth).delete(ids.ids)
    return SuccessResponse("删除成功")


@router.post("/counts/{document_id}/approve", summary="审核库存盘点")
async def count_approve(document_id: int, auth: Auth = Depends(auth_permission("count", "approve"))):
    """按盘点差异生成盘盈盘亏过账。"""

    return SuccessResponse(await count_service(auth).approve(document_id))


@router.post("/counts/{document_id}/unapprove", summary="反审核库存盘点")
async def count_unapprove(document_id: int, auth: Auth = Depends(auth_permission("count", "unapprove"))):
    """冲销盘盈盘亏过账。"""

    return SuccessResponse(await count_service(auth).unapprove(document_id))


@router.get("/other-orders", summary="其他出入库列表")
async def other_list(page: int = 1, limit: int = 20, status: str | None = None, keyword: str | None = None, auth: Auth = Depends(auth_permission("other", "list"))):
    """分页查询其他出入库单。"""

    data, count = await other_service(auth).list(page, limit, status, keyword)
    return SuccessResponse(data, count=count)


@router.get("/other-orders/{document_id}", summary="其他出入库详情")
async def other_detail(document_id: int, auth: Auth = Depends(auth_permission("other", "view"))):
    """返回其他出入库详情。"""

    return SuccessResponse(await other_service(auth).detail(document_id))


@router.post("/other-orders", summary="新增其他出入库")
async def other_create(data: schemas.OtherStockOrderInput, auth: Auth = Depends(auth_permission("other", "create"))):
    """新增其他出入库草稿。"""

    return SuccessResponse(await other_service(auth).save(data))


@router.put("/other-orders/{document_id}", summary="修改其他出入库")
async def other_update(document_id: int, data: schemas.OtherStockOrderInput, auth: Auth = Depends(auth_permission("other", "update"))):
    """修改其他出入库草稿。"""

    return SuccessResponse(await other_service(auth).save(data, document_id))


@router.delete("/other-orders", summary="删除其他出入库")
async def other_delete(ids: IdList = Depends(), auth: Auth = Depends(auth_permission("other", "delete"))):
    """删除其他出入库草稿。"""

    await other_service(auth).delete(ids.ids)
    return SuccessResponse("删除成功")


@router.post("/other-orders/{document_id}/approve", summary="审核其他出入库")
async def other_approve(document_id: int, auth: Auth = Depends(auth_permission("other", "approve"))):
    """审核其他出入库并过账。"""

    return SuccessResponse(await other_service(auth).approve(document_id))


@router.post("/other-orders/{document_id}/unapprove", summary="反审核其他出入库")
async def other_unapprove(document_id: int, auth: Auth = Depends(auth_permission("other", "unapprove"))):
    """冲销其他出入库。"""

    return SuccessResponse(await other_service(auth).unapprove(document_id))
