"""采购管理路由聚合入口。"""

from fastapi import APIRouter
from .api import catalog_router, document_router, finance_router


app = APIRouter()
app.include_router(catalog_router)
app.include_router(document_router)
app.include_router(finance_router)

