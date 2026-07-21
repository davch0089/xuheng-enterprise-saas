"""采购 API 服务依赖工厂。"""

from apps.vadmin.auth.utils.validation.auth import Auth
from ..queries import PurchaseQueryService
from ..services import PurchaseOrderService, PurchasePaymentService, PurchaseReceiptService, PurchaseReturnService


def user_id(auth: Auth):
    """返回当前登录用户 ID。"""

    return auth.user.id if auth.user else None


def order_service(auth):
    """构造采购订单服务。"""

    return PurchaseOrderService(auth.db, user_id(auth))


def receipt_service(auth):
    """构造采购收货服务。"""

    return PurchaseReceiptService(auth.db, user_id(auth))


def return_service(auth):
    """构造采购退货服务。"""

    return PurchaseReturnService(auth.db, user_id(auth))


def payment_service(auth):
    """构造采购付款服务。"""

    return PurchasePaymentService(auth.db, user_id(auth))


def query_service(auth):
    """构造采购只读查询服务。"""

    return PurchaseQueryService(auth.db)

