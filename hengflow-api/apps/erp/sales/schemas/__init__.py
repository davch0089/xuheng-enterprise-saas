"""销售管理输入模型导出。"""

from .documents import SalesDeliveryInput, SalesLineInput, SalesOrderInput, SalesReturnInput
from .receivable import ReceiptAllocationInput, SalesReceiptInput

__all__ = [
    "ReceiptAllocationInput",
    "SalesDeliveryInput",
    "SalesLineInput",
    "SalesOrderInput",
    "SalesReceiptInput",
    "SalesReturnInput",
]
