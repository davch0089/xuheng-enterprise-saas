"""财务资金、核销和会计期间 ORM 实体。"""

from datetime import date, datetime
from decimal import Decimal

from db.db_base import BaseModel
from sqlalchemy import Boolean, DECIMAL, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column


OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


class ErpAccountingPeriod(BaseModel):
    """定义业务过账允许使用的会计日期区间。"""

    __tablename__ = "erp_accounting_period"
    __table_args__ = (UniqueConstraint("period_code", name="uq_erp_accounting_period_code"), {**OPTIONS, "comment": "会计期间"})

    period_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    closed_by_id: Mapped[int | None] = mapped_column(Integer)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    closing_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(String(500))


class ErpFundAccount(BaseModel):
    """保存现金、银行及第三方支付资金账户。"""

    __tablename__ = "erp_fund_account"
    __table_args__ = (UniqueConstraint("code", name="uq_erp_fund_account_code"), {**OPTIONS, "comment": "资金账户"})

    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    account_type: Mapped[str] = mapped_column(String(30), nullable=False, default="bank")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")
    bank_name: Mapped[str | None] = mapped_column(String(100))
    account_no: Mapped[str | None] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remark: Mapped[str | None] = mapped_column(String(500))


class ErpFundAccountBalance(BaseModel):
    """保存每个资金账户的当前余额。"""

    __tablename__ = "erp_fund_account_balance"
    __table_args__ = (UniqueConstraint("account_id", name="uq_erp_fund_account_balance"), {**OPTIONS, "comment": "资金账户余额"})

    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_fund_account.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    last_entry_id: Mapped[int | None] = mapped_column(Integer)
    last_occurred_at: Mapped[datetime | None] = mapped_column(DateTime)


class ErpFundDocument(BaseModel):
    """记录一般收款、一般付款和账户内部转账单。"""

    __tablename__ = "erp_fund_document"
    __table_args__ = (UniqueConstraint("document_no", name="uq_erp_fund_document_no"), {**OPTIONS, "comment": "资金单据"})

    document_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    from_account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_fund_account.id"))
    to_account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_fund_account.id"))
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    counterparty: Mapped[str | None] = mapped_column(String(150))
    profit_category: Mapped[str] = mapped_column(String(30), nullable=False, default="none")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    posting_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by_id: Mapped[int | None] = mapped_column(Integer)
    approved_by_id: Mapped[int | None] = mapped_column(Integer)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(Text)


class ErpFundLedger(BaseModel):
    """记录资金账户的不可变收支与冲销流水。"""

    __tablename__ = "erp_fund_ledger"
    __table_args__ = (
        UniqueConstraint("entry_no", name="uq_erp_fund_ledger_no"),
        UniqueConstraint("idempotency_key", name="uq_erp_fund_ledger_idempotency"),
        {**OPTIONS, "comment": "不可变资金流水"},
    )

    entry_no: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_fund_account.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_no: Mapped[str] = mapped_column(String(60), nullable=False)
    posting_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reversal_of_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_fund_ledger.id", ondelete="RESTRICT"), index=True)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    balance_before: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    operator_id: Mapped[int | None] = mapped_column(Integer)
    remark: Mapped[str | None] = mapped_column(String(500))


class ErpSettlementDocument(BaseModel):
    """记录预收、预付及应收应付对冲核销单。"""

    __tablename__ = "erp_settlement_document"
    __table_args__ = (UniqueConstraint("document_no", name="uq_erp_settlement_document_no"), {**OPTIONS, "comment": "财务核销单"})

    document_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    writeoff_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    customer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_customer.id"))
    supplier_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_supplier.id"))
    source_receipt_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_sales_receipt.id"))
    source_payment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_purchase_payment.id"))
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    posting_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by_id: Mapped[int | None] = mapped_column(Integer)
    approved_by_id: Mapped[int | None] = mapped_column(Integer)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(String(500))


class ErpSettlementAllocation(BaseModel):
    """记录核销单对应的应收或应付开放项目金额。"""

    __tablename__ = "erp_settlement_allocation"
    __table_args__ = (UniqueConstraint("document_id", "target_type", "target_id", name="uq_erp_settlement_allocation"), {**OPTIONS, "comment": "财务核销明细"})

    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_settlement_document.id", ondelete="CASCADE"), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)


@event.listens_for(ErpFundLedger, "before_update")
@event.listens_for(ErpFundLedger, "before_delete")
def prevent_fund_ledger_change(*_):
    """禁止修改或删除资金流水，只允许生成反向冲销。"""

    raise RuntimeError("资金流水不可修改或删除；请通过反向冲销更正")
