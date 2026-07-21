"""库存查询聚合服务。"""

from .balances import BalanceQueryMixin
from .base import InventoryQueryBase
from .movements import MovementQueryMixin
from .tracking import TrackingQueryMixin


class InventoryQueryService(
    InventoryQueryBase,
    BalanceQueryMixin,
    MovementQueryMixin,
    TrackingQueryMixin,
):
    """聚合库存余额、流水、批次和序列号读模型。"""

    pass
