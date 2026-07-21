"""库存过账兼容入口；新代码可从 services.stock 导入。"""

from .services.stock import MovementType, PostingRequest, StockMovement, StockPostingEngine

__all__ = ["MovementType", "PostingRequest", "StockMovement", "StockPostingEngine"]
