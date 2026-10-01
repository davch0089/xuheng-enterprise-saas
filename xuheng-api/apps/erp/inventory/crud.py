"""入库服务兼容入口；新代码可从 services.inbound 导入。"""

from .services.inbound import InventoryService

__all__ = ["InventoryService"]
