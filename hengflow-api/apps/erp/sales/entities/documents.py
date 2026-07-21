"""销售订单、出库单和退货单 ORM 实体。"""

from datetime import date, datetime
from decimal import Decimal

from db.db_base import BaseModel
from sqlalchemy import DECIMAL, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


class SalesDocumentMixin:
    """销售业务单据共用的客户、金额、状态和审核字段。"""

    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_customer.id"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_warehouse.id"), nullable=False)
    employee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_employee.id"))
    delivery_address: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    total_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    payable_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(Integer)
    approved_by_id: Mapped[int | None] = mapped_column(Integer)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    posting_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SalesLineMixin:
    """销售业务明细共用的单位换算、售价、折扣和税额字段。"""

    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_product.id"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_warehouse.id"), nullable=False)
    unit_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_unit.id"), nullable=False)
    unit_to_base_rate: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    base_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    discount_rate: Mapped[Decimal] = mapped_column(DECIMAL(10, 4), nullable=False, default=100)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    tax_rate: Mapped[Decimal] = mapped_column(DECIMAL(10, 4), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    tax_inclusive_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(String(500))


class ErpSalesOrder(SalesDocumentMixin, BaseModel):
    """记录销售订单及其履约状态。"""

    __tablename__ = "erp_sales_order"
    __table_args__ = (
        UniqueConstraint("order_no", name="uq_erp_sales_order_no"),
        {**OPTIONS, "comment": "销售订单"},
    )

    order_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date)


class ErpSalesOrderLine(SalesLineMixin, BaseModel):
    """记录销售订单商品、预留量和累计出库量。"""

    __tablename__ = "erp_sales_order_line"
    __table_args__ = (
        UniqueConstraint("order_id", "line_no", name="uq_erp_sales_order_line_no"),
        {**OPTIONS, "comment": "销售订单明细"},
    )

    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("erp_sales_order.id", ondelete="CASCADE"), nullable=False, index=True
    )
    delivered_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)


class ErpSalesDelivery(SalesDocumentMixin, BaseModel):
    """记录实际销售出库及其库存和应收过账状态。"""

    __tablename__ = "erp_sales_delivery"
    __table_args__ = (
        UniqueConstraint("delivery_no", name="uq_erp_sales_delivery_no"),
        {**OPTIONS, "comment": "销售出库单"},
    )

    delivery_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_sales_order.id"), index=True)
    due_date: Mapped[date | None] = mapped_column(Date)
    batch_selection_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="auto", comment="批次选择模式：auto/manual"
    )
    total_cost: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    gross_profit: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    settlement_discount_rate: Mapped[Decimal] = mapped_column(DECIMAL(10, 4), nullable=False, default=100)
    settlement_discount_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    rounding_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    settlement_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    current_payment_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    settlement_method_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_settlement_method.id"))
    fund_account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_fund_account.id"), index=True)
    linked_receipt_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_sales_receipt.id"), index=True)


class ErpSalesDeliveryLine(SalesLineMixin, BaseModel):
    """记录销售出库明细、批次序列号和实际出库成本。"""

    __tablename__ = "erp_sales_delivery_line"
    __table_args__ = (
        UniqueConstraint("delivery_id", "line_no", name="uq_erp_sales_delivery_line_no"),
        {**OPTIONS, "comment": "销售出库单明细"},
    )

    delivery_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("erp_sales_delivery.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_line_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_sales_order_line.id"), index=True)
    batch_no: Mapped[str | None] = mapped_column(String(80))
    serial_numbers: Mapped[str | None] = mapped_column(Text)
    unit_cost: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    cost_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    returned_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)


class ErpSalesReturn(SalesDocumentMixin, BaseModel):
    """记录客户退货及其库存和红字应收过账状态。"""

    __tablename__ = "erp_sales_return"
    __table_args__ = (
        UniqueConstraint("return_no", name="uq_erp_sales_return_no"),
        {**OPTIONS, "comment": "销售退货单"},
    )

    return_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    delivery_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_sales_delivery.id"), nullable=False, index=True)
    total_cost: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)


class ErpSalesReturnLine(SalesLineMixin, BaseModel):
    """记录退货商品、原出库明细和回库成本。"""

    __tablename__ = "erp_sales_return_line"
    __table_args__ = (
        UniqueConstraint("return_id", "line_no", name="uq_erp_sales_return_line_no"),
        {**OPTIONS, "comment": "销售退货单明细"},
    )

    return_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("erp_sales_return.id", ondelete="CASCADE"), nullable=False, index=True
    )
    delivery_line_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("erp_sales_delivery_line.id"), nullable=False, index=True
    )
    batch_no: Mapped[str | None] = mapped_column(String(80))
    serial_numbers: Mapped[str | None] = mapped_column(Text)
    unit_cost: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    cost_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)


class ErpStockReservation(BaseModel):
    """记录销售订单明细对仓库商品库存的预留和释放情况。"""

    __tablename__ = "erp_stock_reservation"
    __table_args__ = (
        UniqueConstraint("source_type", "source_line_id", name="uq_erp_stock_reservation_source"),
        {**OPTIONS, "comment": "库存预留"},
    )

    source_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_line_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_warehouse.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_product.id"), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    released_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
