"""旧库存公共工具兼容入口；新代码应使用 apps.erp.common。"""

from apps.erp.common import COST, MONEY, QTY, quantize

__all__ = ["COST", "MONEY", "QTY", "quantize"]
