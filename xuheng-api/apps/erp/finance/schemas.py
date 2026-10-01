"""资金、核销和会计期间输入模型。"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class FundAccountInput(BaseModel):
    """资金账户输入。"""

    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    account_type: str = "bank"
    currency: str = "CNY"
    bank_name: str | None = None
    account_no: str | None = None
    opening_balance: Decimal = 0
    is_active: bool = True
    remark: str | None = None


class FundDocumentInput(BaseModel):
    """一般收款、付款或转账输入。"""

    document_no: str | None = None
    document_type: str
    business_date: date
    from_account_id: int | None = None
    to_account_id: int | None = None
    amount: Decimal = Field(gt=0)
    counterparty: str | None = None
    profit_category: str = "none"
    remark: str | None = None

    @model_validator(mode="after")
    def validate_accounts(self):
        """校验不同资金单据要求的收付款账户。"""

        if self.document_type == "receipt" and not self.to_account_id:
            raise ValueError("收款必须选择收款账户")
        if self.document_type == "payment" and not self.from_account_id:
            raise ValueError("付款必须选择付款账户")
        if self.document_type == "transfer":
            if not self.from_account_id or not self.to_account_id:
                raise ValueError("转账必须选择转出和转入账户")
            if self.from_account_id == self.to_account_id:
                raise ValueError("转出和转入账户不能相同")
        return self


class SettlementAllocationInput(BaseModel):
    """应收或应付开放项目核销输入。"""

    target_type: str
    target_id: int
    amount: Decimal = Field(gt=0)


class SettlementDocumentInput(BaseModel):
    """预收、预付或应收应付对冲输入。"""

    document_no: str | None = None
    writeoff_type: str
    business_date: date
    customer_id: int | None = None
    supplier_id: int | None = None
    source_receipt_id: int | None = None
    source_payment_id: int | None = None
    amount: Decimal = Field(gt=0)
    allocations: list[SettlementAllocationInput] = Field(min_length=1)
    remark: str | None = None


class AccountingPeriodInput(BaseModel):
    """会计期间输入。"""

    period_code: str = Field(min_length=1, max_length=20)
    start_date: date
    end_date: date
    remark: str | None = None

    @model_validator(mode="after")
    def validate_range(self):
        """保证期间结束日期不早于开始日期。"""

        if self.end_date < self.start_date:
            raise ValueError("期间结束日期不能早于开始日期")
        return self
