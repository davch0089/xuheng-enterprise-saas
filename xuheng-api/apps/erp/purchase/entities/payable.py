"""供应商应付、付款与不可变流水 ORM 实体。"""

from datetime import date, datetime
from decimal import Decimal

from db.db_base import BaseModel
from sqlalchemy import DECIMAL, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column


OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


class ErpSupplierPayableBalance(BaseModel):
    """保存供应商维度的应付余额。"""

    __tablename__ = "erp_supplier_payable_balance"
    __table_args__ = (UniqueConstraint("supplier_id", name="uq_erp_supplier_payable_balance"), {**OPTIONS, "comment": "供应商应付余额"})

    supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_supplier.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    last_entry_id: Mapped[int | None] = mapped_column(Integer)
    last_occurred_at: Mapped[datetime | None] = mapped_column(DateTime)


class ErpPayable(BaseModel):
    """采购收货形成的供应商应付开放项目。"""

    __tablename__ = "erp_payable"
    __table_args__ = (UniqueConstraint("receipt_id", name="uq_erp_payable_receipt"), {**OPTIONS, "comment": "供应商应付项目"})

    payable_no: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_supplier.id"), nullable=False, index=True)
    receipt_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_purchase_receipt.id"), nullable=False)
    receipt_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    original_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    settled_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    returned_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    outstanding_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)


class ErpPayableLedger(BaseModel):
    """记录应付增加、退货、付款和冲销的不可变流水。"""

    __tablename__ = "erp_payable_ledger"
    __table_args__ = (
        UniqueConstraint("entry_no", name="uq_erp_payable_ledger_no"),
        UniqueConstraint("idempotency_key", name="uq_erp_payable_ledger_idempotency"),
        {**OPTIONS, "comment": "不可变应付流水"},
    )

    entry_no: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_supplier.id"), nullable=False, index=True)
    payable_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_payable.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_no: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    posting_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reversal_of_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_payable_ledger.id", ondelete="RESTRICT"), index=True)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    balance_before: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    operator_id: Mapped[int | None] = mapped_column(Integer)
    remark: Mapped[str | None] = mapped_column(String(500))


class ErpPurchasePayment(BaseModel):
    """记录供应商付款单及审核信息。"""

    __tablename__ = "erp_purchase_payment"
    __table_args__ = (UniqueConstraint("payment_no", name="uq_erp_purchase_payment_no"), {**OPTIONS, "comment": "采购付款单"})

    payment_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_supplier.id"), nullable=False, index=True)
    settlement_method_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_settlement_method.id"))
    fund_account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_fund_account.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    remark: Mapped[str | None] = mapped_column(String(500))
    created_by_id: Mapped[int | None] = mapped_column(Integer)
    approved_by_id: Mapped[int | None] = mapped_column(Integer)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    posting_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ErpPurchasePaymentAllocation(BaseModel):
    """记录付款对具体应付项目的核销金额。"""

    __tablename__ = "erp_purchase_payment_allocation"
    __table_args__ = (UniqueConstraint("payment_id", "payable_id", name="uq_erp_purchase_payment_allocation"), {**OPTIONS, "comment": "采购付款核销明细"})

    payment_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_purchase_payment.id", ondelete="CASCADE"), nullable=False, index=True)
    payable_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_payable.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)


@event.listens_for(ErpPayableLedger, "before_update")
def prevent_payable_ledger_update(*_):
    """禁止修改已经生成的应付流水。"""

    raise RuntimeError("应付流水不可修改；请通过冲销流水更正")


@event.listens_for(ErpPayableLedger, "before_delete")
def prevent_payable_ledger_delete(*_):
    """禁止删除已经生成的应付流水。"""

    raise RuntimeError("应付流水不可删除；请通过冲销流水更正")
