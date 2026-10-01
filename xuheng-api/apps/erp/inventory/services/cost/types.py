"""成本引擎请求、结果和成本类型定义。"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from ... import models


class CostType(str, Enum):
    """库存成本流水的标准业务类型。"""

    RECEIPT = "RECEIPT"
    ISSUE = "ISSUE"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    ADJUSTMENT = "ADJUSTMENT"
    REVALUATION = "REVALUATION"
    REVERSAL = "REVERSAL"


@dataclass(frozen=True)
class CostMovementRequest:
    """描述库存收发传递给成本引擎的计价请求。"""

    idempotency_key: str
    cost_no: str
    cost_type: CostType
    source_type: str
    source_id: int
    source_no: str
    source_line_id: int
    cost_role: str
    posting_version: int
    warehouse_id: int
    product_id: int
    direction: int
    quantity: Decimal
    amount: Decimal | None = None
    unit_cost: Decimal | None = None
    expected_quantity_before: Decimal | None = None
    occurred_at: datetime = field(default_factory=datetime.now)
    operator_id: int | None = None
    remark: str | None = None


@dataclass(frozen=True)
class CostAdjustmentRequest:
    """描述仅改变库存价值的成本调整请求。"""

    idempotency_key: str
    cost_no: str
    source_type: str
    source_id: int
    source_no: str
    posting_version: int
    warehouse_id: int
    product_id: int
    amount: Decimal
    source_line_id: int = 0
    cost_role: str = "cost_adjustment"
    occurred_at: datetime = field(default_factory=datetime.now)
    operator_id: int | None = None
    remark: str | None = None


@dataclass(frozen=True)
class CostRevaluationRequest:
    """描述按目标移动平均价重新计价的请求。"""

    idempotency_key: str
    cost_no: str
    source_type: str
    source_id: int
    source_no: str
    posting_version: int
    warehouse_id: int
    product_id: int
    target_average_cost: Decimal
    source_line_id: int = 0
    cost_role: str = "revaluation"
    occurred_at: datetime = field(default_factory=datetime.now)
    operator_id: int | None = None
    remark: str | None = None


@dataclass
class CostPostingResult:
    """返回成本过账流水及过账前后的成本快照。"""

    ledger: models.ErpInventoryCostLedger
    balance: models.ErpInventoryCostBalance
    quantity_before: Decimal
    quantity_after: Decimal
    value_before: Decimal
    value_after: Decimal
    average_cost_before: Decimal
    average_cost_after: Decimal
    signed_amount: Decimal
    is_replay: bool = False
