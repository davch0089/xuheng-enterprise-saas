"""旧精度工具兼容入口；新代码应从 apps.erp.common 导入。"""

from apps.erp.common.precision import COST, MONEY, QTY, quantize

__all__ = ["COST", "MONEY", "QTY", "quantize"]
