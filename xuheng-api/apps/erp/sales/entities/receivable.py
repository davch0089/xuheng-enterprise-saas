"""客户应收、收款及核销 ORM 实体。"""

from datetime import date, datetime
from decimal import Decimal

from db.db_base import BaseModel
from sqlalchemy import DECIMAL, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column


OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


class ErpCustomerReceivableBalance(BaseModel):
    """客户维度的应收余额。"""

    __tablename__ = "erp_customer_receivable_balance"
    __table_args__ = (
        UniqueConstraint("customer_id", name="uq_erp_customer_receivable_balance"),
        {**OPTIONS, "comment": "客户应收余额"},
    )

    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_customer.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    last_entry_id: Mapped[int | None] = mapped_column(Integer)
    last_occurred_at: Mapped[datetime | None] = mapped_column(DateTime)


class ErpReceivable(BaseModel):
    """销售出库形成的客户应收开放项目。"""

    __tablename__ = "erp_receivable"
    __table_args__ = (
        UniqueConstraint("delivery_id", name="uq_erp_receivable_delivery"),
        {**OPTIONS, "comment": "客户应收项目"},
    )

    receivable_no: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_customer.id"), nullable=False, index=True)
    delivery_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_sales_delivery.id"), nullable=False)
    delivery_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    original_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    settled_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    returned_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    outstanding_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)


class ErpReceivableLedger(BaseModel):
    """记录不可变的应收增加、退货、收款和冲销流水。"""

    __tablename__ = "erp_receivable_ledger"
    __table_args__ = (
        UniqueConstraint("entry_no", name="uq_erp_receivable_ledger_no"),
        UniqueConstraint("idempotency_key", name="uq_erp_receivable_ledger_idempotency"),
        {**OPTIONS, "comment": "不可变应收流水"},
    )

    entry_no: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_customer.id"), nullable=False, index=True)
    receivable_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_receivable.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_no: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    posting_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reversal_of_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("erp_receivable_ledger.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    balance_before: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    operator_id: Mapped[int | None] = mapped_column(Integer)
    remark: Mapped[str | None] = mapped_column(String(500))


class ErpSalesReceipt(BaseModel):
    """记录客户收款单及其审核状态。"""

    __tablename__ = "erp_sales_receipt"
    __table_args__ = (
        UniqueConstraint("receipt_no", name="uq_erp_sales_receipt_no"),
        {**OPTIONS, "comment": "销售收款单"},
    )

    receipt_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_customer.id"), nullable=False, index=True)
    settlement_method_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_settlement_method.id"))
    fund_account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_fund_account.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    remark: Mapped[str | None] = mapped_column(String(500))
    created_by_id: Mapped[int | None] = mapped_column(Integer)
    approved_by_id: Mapped[int | None] = mapped_column(Integer)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    posting_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ErpSalesReceiptAllocation(BaseModel):
    """记录一笔收款对具体应收项目的核销金额。"""

    __tablename__ = "erp_sales_receipt_allocation"
    __table_args__ = (
        UniqueConstraint("receipt_id", "receivable_id", name="uq_erp_sales_receipt_allocation"),
        {**OPTIONS, "comment": "销售收款核销明细"},
    )

    receipt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("erp_sales_receipt.id", ondelete="CASCADE"), nullable=False, index=True
    )
    receivable_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_receivable.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)


@event.listens_for(ErpReceivableLedger, "before_update")
def prevent_receivable_ledger_update(*_):
    """禁止修改已经生成的应收流水。"""

    raise RuntimeError("应收流水不可修改；请通过冲销流水更正")


@event.listens_for(ErpReceivableLedger, "before_delete")
def prevent_receivable_ledger_delete(*_):
    """禁止删除已经生成的应收流水。"""

    raise RuntimeError("应收流水不可删除；请通过冲销流水更正")
