"""库存过账的数据对象和统一移动类型。"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Sequence


class MovementType(str, Enum):
    """ERP 支持的标准库存移动类型。"""

    PURCHASE_IN = "PURCHASE_IN"
    OTHER_IN = "OTHER_IN"
    SALE_RETURN = "SALE_RETURN"
    STOCK_GAIN = "STOCK_GAIN"
    PRODUCTION_IN = "PRODUCTION_IN"
    TRANSFER_IN = "TRANSFER_IN"

    SALE_OUT = "SALE_OUT"
    OTHER_OUT = "OTHER_OUT"
    PURCHASE_RETURN = "PURCHASE_RETURN"
    STOCK_LOSS = "STOCK_LOSS"
    MATERIAL_OUT = "MATERIAL_OUT"
    TRANSFER_OUT = "TRANSFER_OUT"

    REVERSAL = "REVERSAL"


INBOUND_TYPES = {
    MovementType.PURCHASE_IN,
    MovementType.OTHER_IN,
    MovementType.SALE_RETURN,
    MovementType.STOCK_GAIN,
    MovementType.PRODUCTION_IN,
    MovementType.TRANSFER_IN,
}
OUTBOUND_TYPES = {
    MovementType.SALE_OUT,
    MovementType.OTHER_OUT,
    MovementType.PURCHASE_RETURN,
    MovementType.STOCK_LOSS,
    MovementType.MATERIAL_OUT,
    MovementType.TRANSFER_OUT,
}


@dataclass(frozen=True)
class StockMovement:
    """描述一条标准化的库存数量变动。"""

    movement_type: MovementType
    business_line_id: int
    product_id: int
    warehouse_id: int
    quantity: Decimal
    amount: Decimal | None = None
    unit_cost: Decimal | None = None
    movement_role: str = "main"
    batch_no: str | None = None
    production_date: date | None = None
    expiry_date: date | None = None
    serial_numbers: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PostingRequest:
    """封装一个业务单据本次审核产生的全部库存移动。"""

    source_type: str
    source_id: int
    source_no: str
    posting_version: int
    movements: Sequence[StockMovement]
    occurred_at: datetime = field(default_factory=datetime.now)
    operator_id: int | None = None
