"""采购表单选项和来源单据接口。"""

from fastapi import APIRouter, Depends
from apps.vadmin.auth.utils.current import AllUserAuth, FullAdminAuth
from apps.vadmin.auth.utils.validation.auth import Auth
from utils.response import SuccessResponse
from .dependencies import query_service


router = APIRouter()


@router.get("/options")
async def options(auth: Auth = Depends(AllUserAuth())):
    """返回采购业务基础资料选项。"""

    return SuccessResponse(await query_service(auth).options())


@router.get("/products")
async def products(keyword: str | None = None, warehouse_id: int | None = None, limit: int = 100, auth: Auth = Depends(AllUserAuth())):
    """搜索可采购商品。"""

    return SuccessResponse(await query_service(auth).products(keyword, warehouse_id, limit))


@router.get("/source-orders")
async def source_orders(supplier_id: int | None = None, auth: Auth = Depends(FullAdminAuth(permissions=["erp.purchase.receipt.list"]))):
    """返回可以继续收货的采购订单。"""

    return SuccessResponse(await query_service(auth).source_orders(supplier_id))


@router.get("/source-receipts")
async def source_receipts(supplier_id: int | None = None, auth: Auth = Depends(FullAdminAuth(permissions=["erp.purchase.return.list"]))):
    """返回存在可退数量的采购收货单。"""

    return SuccessResponse(await query_service(auth).source_receipts(supplier_id))
