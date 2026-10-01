"""序衡主线接口。"""

from fastapi import APIRouter, Depends

from apps.vadmin.auth.utils.current import FullAdminAuth
from apps.vadmin.auth.utils.validation.auth import Auth
from utils.response import SuccessResponse

from .schemas import OrderIn, ProductIn, StockAdjustIn, TenantIn
from .services import XuhengService

app = APIRouter()


@app.get("/tenants", summary="我的企业")
async def list_tenants(auth: Auth = Depends(FullAdminAuth())):
    return SuccessResponse(await XuhengService(auth.db, auth.user).list_tenants())


@app.post("/tenants", summary="创建企业")
async def create_tenant(data: TenantIn, auth: Auth = Depends(FullAdminAuth())):
    return SuccessResponse(await XuhengService(auth.db, auth.user).create_tenant(data.code, data.name))


@app.get("/products", summary="企业商品")
async def list_products(tenant_id: int, auth: Auth = Depends(FullAdminAuth())):
    return SuccessResponse(await XuhengService(auth.db, auth.user).list_products(tenant_id))


@app.post("/products", summary="新增商品")
async def create_product(data: ProductIn, auth: Auth = Depends(FullAdminAuth())):
    return SuccessResponse(await XuhengService(auth.db, auth.user).create_product(data))


@app.post("/stocks/receive", summary="数量入库")
async def receive_stock(data: StockAdjustIn, auth: Auth = Depends(FullAdminAuth())):
    return SuccessResponse(await XuhengService(auth.db, auth.user).receive_stock(
        data.tenant_id, data.product_id, data.quantity
    ))


@app.get("/orders", summary="企业订单")
async def list_orders(tenant_id: int, auth: Auth = Depends(FullAdminAuth())):
    return SuccessResponse(await XuhengService(auth.db, auth.user).list_orders(tenant_id))


@app.post("/orders", summary="创建待确认订单")
async def create_order(data: OrderIn, auth: Auth = Depends(FullAdminAuth())):
    return SuccessResponse(await XuhengService(auth.db, auth.user).create_order(data))


@app.post("/orders/{order_id}/confirm", summary="确认订单")
async def confirm_order(order_id: int, tenant_id: int, auth: Auth = Depends(FullAdminAuth())):
    return SuccessResponse(await XuhengService(auth.db, auth.user).confirm(tenant_id, order_id))


@app.post("/orders/{order_id}/ship", summary="发货并减少库存")
async def ship_order(order_id: int, tenant_id: int, auth: Auth = Depends(FullAdminAuth())):
    return SuccessResponse(await XuhengService(auth.db, auth.user).ship(tenant_id, order_id))


@app.post("/orders/{order_id}/close", summary="关闭未发货订单")
async def close_order(order_id: int, tenant_id: int, auth: Auth = Depends(FullAdminAuth())):
    return SuccessResponse(await XuhengService(auth.db, auth.user).close(tenant_id, order_id))


@app.post("/orders/{order_id}/return", summary="退货并加回库存")
async def return_order(order_id: int, tenant_id: int, auth: Auth = Depends(FullAdminAuth())):
    return SuccessResponse(await XuhengService(auth.db, auth.user).return_order(tenant_id, order_id))
