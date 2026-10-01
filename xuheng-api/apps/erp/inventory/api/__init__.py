"""库存 HTTP 路由。"""

from .inbound import router as inbound_router
from .stock import router as stock_router
from .operations import router as operations_router
from .assembly import router as assembly_router

__all__ = ["inbound_router", "stock_router", "operations_router", "assembly_router"]
