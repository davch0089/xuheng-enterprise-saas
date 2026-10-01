"""采购、销售、库存和财务模块共享的 ERP 基础能力。"""

from .precision import COST, MONEY, QTY, quantize

__all__ = ["COST", "MONEY", "QTY", "quantize"]
