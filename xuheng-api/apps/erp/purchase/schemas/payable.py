"""供应商付款和应付核销输入模型。"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class PaymentAllocationInput(BaseModel):
    """一条付款对应的应付核销金额。"""

    payable_id: int
    amount: Decimal = Field(gt=0)


class PurchasePaymentInput(BaseModel):
    """供应商付款单输入。"""

    payment_no: str | None = Field(default=None, max_length=50)
    payment_date: date
    supplier_id: int
    settlement_method_id: int | None = None
    fund_account_id: int | None = None
    amount: Decimal = Field(gt=0)
    remark: str | None = Field(default=None, max_length=500)
    allocations: list[PaymentAllocationInput] = Field(default_factory=list)
