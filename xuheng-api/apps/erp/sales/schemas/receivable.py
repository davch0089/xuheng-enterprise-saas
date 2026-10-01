"""收款和应收核销输入模型。"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class ReceiptAllocationInput(BaseModel):
    """一条收款对应的应收核销输入。"""

    receivable_id: int
    amount: Decimal = Field(gt=0)


class SalesReceiptInput(BaseModel):
    """客户收款单和可选核销明细输入。"""

    receipt_no: str | None = None
    receipt_date: date
    customer_id: int
    settlement_method_id: int | None = None
    fund_account_id: int | None = None
    amount: Decimal = Field(gt=0)
    allocations: list[ReceiptAllocationInput] = Field(default_factory=list)
    remark: str | None = None

    @field_validator("receipt_no", mode="before")
    @classmethod
    def empty_number_to_none(cls, value):
        """将空收款单号转换为空值以便自动编号。"""

        return value.strip() if isinstance(value, str) and value.strip() else None
