"""库存模块路由聚合入口。"""

from fastapi import APIRouter

from .api import assembly_router, inbound_router, operations_router, stock_router


app = APIRouter()
app.include_router(inbound_router)
app.include_router(stock_router)
app.include_router(operations_router)
app.include_router(assembly_router)
