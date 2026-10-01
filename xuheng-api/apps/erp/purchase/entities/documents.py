"""采购订单、收货和退货 ORM 实体。"""

from datetime import date, datetime
from decimal import Decimal

from db.db_base import BaseModel
from sqlalchemy import DECIMAL, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


class PurchaseDocumentMixin:
    """采购业务单据共用的供应商、仓库、金额和审核字段。"""

    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_supplier.id"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_warehouse.id"), nullable=False)
    employee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_employee.id"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    total_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    payable_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(Integer)
    approved_by_id: Mapped[int | None] = mapped_column(Integer)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    posting_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PurchaseLineMixin:
    """采购明细共用的单位换算、价格和税额字段。"""

    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_product.id"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_warehouse.id"), nullable=False)
    unit_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_unit.id"), nullable=False)
    unit_to_base_rate: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    base_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    tax_rate: Mapped[Decimal] = mapped_column(DECIMAL(10, 4), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    tax_inclusive_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(String(500))


class ErpPurchaseOrder(PurchaseDocumentMixin, BaseModel):
    """记录采购订单和累计收货状态。"""

    __tablename__ = "erp_purchase_order"
    __table_args__ = (UniqueConstraint("order_no", name="uq_erp_purchase_order_no"), {**OPTIONS, "comment": "采购订单"})

    order_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    expected_receipt_date: Mapped[date | None] = mapped_column(Date)


class ErpPurchaseOrderLine(PurchaseLineMixin, BaseModel):
    """记录采购订单商品和累计收货主单位数量。"""

    __tablename__ = "erp_purchase_order_line"
    __table_args__ = (UniqueConstraint("order_id", "line_no", name="uq_erp_purchase_order_line_no"), {**OPTIONS, "comment": "采购订单明细"})

    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_purchase_order.id", ondelete="CASCADE"), nullable=False, index=True)
    received_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)


class ErpPurchaseReceipt(PurchaseDocumentMixin, BaseModel):
    """记录采购订单的分批收货、库存和应付过账状态。"""

    __tablename__ = "erp_purchase_receipt"
    __table_args__ = (UniqueConstraint("receipt_no", name="uq_erp_purchase_receipt_no"), {**OPTIONS, "comment": "采购收货单"})

    receipt_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_purchase_order.id"), index=True)
    due_date: Mapped[date | None] = mapped_column(Date)
    settlement_discount_rate: Mapped[Decimal] = mapped_column(DECIMAL(10, 4), nullable=False, default=100)
    settlement_discount_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    rounding_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    settlement_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    current_payment_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    settlement_method_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_settlement_method.id"))
    fund_account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_fund_account.id"), index=True)
    linked_payment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_purchase_payment.id"), index=True)


class ErpPurchaseReceiptLine(PurchaseLineMixin, BaseModel):
    """记录采购收货明细、订单来源和批次序列号。"""

    __tablename__ = "erp_purchase_receipt_line"
    __table_args__ = (UniqueConstraint("receipt_id", "line_no", name="uq_erp_purchase_receipt_line_no"), {**OPTIONS, "comment": "采购收货明细"})

    receipt_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_purchase_receipt.id", ondelete="CASCADE"), nullable=False, index=True)
    order_line_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_purchase_order_line.id"), index=True)
    batch_no: Mapped[str | None] = mapped_column(String(80))
    production_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    serial_numbers: Mapped[str | None] = mapped_column(Text)
    returned_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)


class ErpPurchaseReturn(PurchaseDocumentMixin, BaseModel):
    """记录向供应商退货及其库存和红字应付状态。"""

    __tablename__ = "erp_purchase_return"
    __table_args__ = (UniqueConstraint("return_no", name="uq_erp_purchase_return_no"), {**OPTIONS, "comment": "采购退货单"})

    return_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    receipt_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_purchase_receipt.id"), nullable=False, index=True)


class ErpPurchaseReturnLine(PurchaseLineMixin, BaseModel):
    """记录采购退货商品、原收货行和跟踪属性。"""

    __tablename__ = "erp_purchase_return_line"
    __table_args__ = (UniqueConstraint("return_id", "line_no", name="uq_erp_purchase_return_line_no"), {**OPTIONS, "comment": "采购退货明细"})

    return_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_purchase_return.id", ondelete="CASCADE"), nullable=False, index=True)
    receipt_line_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_purchase_receipt_line.id"), nullable=False, index=True)
    batch_no: Mapped[str | None] = mapped_column(String(80))
    serial_numbers: Mapped[str | None] = mapped_column(Text)
