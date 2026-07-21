"""销售 HTTP 路由导出。"""

from .catalog import router as catalog_router
from .documents import router as document_router
from .finance import router as finance_router

__all__ = ["catalog_router", "document_router", "finance_router"]
