"""销售 API 应用服务依赖工厂。"""

from apps.vadmin.auth.utils.validation.auth import Auth

from ..queries import SalesQueryService
from ..services import (
    SalesDeliveryService,
    SalesOrderService,
    SalesReceiptService,
    SalesReturnService,
)


def user_id(auth: Auth) -> int | None:
    """取得当前登录用户 ID。"""

    return auth.user.id if auth.user else None


def order_service(auth: Auth) -> SalesOrderService:
    """构造销售订单服务。"""

    return SalesOrderService(auth.db, user_id(auth))


def delivery_service(auth: Auth) -> SalesDeliveryService:
    """构造销售出库服务。"""

    return SalesDeliveryService(auth.db, user_id(auth))


def return_service(auth: Auth) -> SalesReturnService:
    """构造销售退货服务。"""

    return SalesReturnService(auth.db, user_id(auth))


def receipt_service(auth: Auth) -> SalesReceiptService:
    """构造销售收款服务。"""

    return SalesReceiptService(auth.db, user_id(auth))


def query_service(auth: Auth) -> SalesQueryService:
    """构造销售只读查询服务。"""

    return SalesQueryService(auth.db)
