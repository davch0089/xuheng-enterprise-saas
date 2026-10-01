"""库存 API 依赖工厂。"""

from apps.vadmin.auth.utils.validation.auth import Auth

from ..queries import InventoryQueryService
from ..services.inbound import InventoryService
from ..services.operations import InventoryCountService, OtherStockOrderService, StockTransferService
from ..services.assembly import AssemblyOrderService, BomService


def service(auth: Auth) -> InventoryService:
    """使用当前请求事务构造入库应用服务。"""

    return InventoryService(auth.db, auth.user.id if auth.user else None)


def query_service(auth: Auth) -> InventoryQueryService:
    """使用当前请求事务构造库存查询服务。"""

    return InventoryQueryService(auth.db)


def transfer_service(auth: Auth) -> StockTransferService:
    """构造库存调拨应用服务。"""

    return StockTransferService(auth.db, auth.user.id if auth.user else None)


def count_service(auth: Auth) -> InventoryCountService:
    """构造库存盘点应用服务。"""

    return InventoryCountService(auth.db, auth.user.id if auth.user else None)


def other_service(auth: Auth) -> OtherStockOrderService:
    """构造其他出入库应用服务。"""

    return OtherStockOrderService(auth.db, auth.user.id if auth.user else None)


def bom_service(auth: Auth) -> BomService:
    """构造BOM维护服务。"""

    return BomService(auth.db, auth.user.id if auth.user else None)


def assembly_service(auth: Auth) -> AssemblyOrderService:
    """构造组装拆卸工单服务。"""

    return AssemblyOrderService(auth.db, auth.user.id if auth.user else None)
