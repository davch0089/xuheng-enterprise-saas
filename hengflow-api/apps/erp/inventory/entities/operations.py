"""调拨、盘点和其他出入库库存作业实体。"""

from datetime import date, datetime
from decimal import Decimal

from db.db_base import BaseModel
from sqlalchemy import DECIMAL, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


class ErpStockTransfer(BaseModel):
    """保存一步或两步调拨单表头及过账阶段。"""

    __tablename__ = "erp_stock_transfer"
    __table_args__ = (
        UniqueConstraint("transfer_no", name="uq_erp_stock_transfer_no"),
        {**OPTIONS, "comment": "库存调拨单"},
    )

    transfer_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    transfer_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    transfer_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="one_step")
    source_warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_warehouse.id"), nullable=False)
    destination_warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_warehouse.id"), nullable=False)
    employee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_employee.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    total_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(Integer)
    dispatched_by_id: Mapped[int | None] = mapped_column(Integer)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime)
    received_by_id: Mapped[int | None] = mapped_column(Integer)
    received_at: Mapped[datetime | None] = mapped_column(DateTime)
    posting_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ErpStockTransferLine(BaseModel):
    """保存调拨商品、单位、批次、序列号及实际转移成本。"""

    __tablename__ = "erp_stock_transfer_line"
    __table_args__ = (
        UniqueConstraint("transfer_id", "line_no", name="uq_erp_stock_transfer_line_no"),
        {**OPTIONS, "comment": "库存调拨明细"},
    )

    transfer_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_stock_transfer.id", ondelete="CASCADE"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_product.id"), nullable=False, index=True)
    unit_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_unit.id"), nullable=False)
    unit_to_base_rate: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    base_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    transfer_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    batch_no: Mapped[str | None] = mapped_column(String(80))
    production_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    serial_numbers: Mapped[str | None] = mapped_column(Text)
    remark: Mapped[str | None] = mapped_column(String(500))


class ErpInventoryCount(BaseModel):
    """保存仓库盘点单、快照汇总和差异过账状态。"""

    __tablename__ = "erp_inventory_count"
    __table_args__ = (
        UniqueConstraint("count_no", name="uq_erp_inventory_count_no"),
        {**OPTIONS, "comment": "库存盘点单"},
    )

    count_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    count_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_warehouse.id"), nullable=False)
    employee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_employee.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    total_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_system_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    total_counted_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    total_gain_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    total_loss_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(Integer)
    approved_by_id: Mapped[int | None] = mapped_column(Integer)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    posting_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ErpInventoryCountLine(BaseModel):
    """保存盘点时点账面快照、实盘数量和跟踪维度差异。"""

    __tablename__ = "erp_inventory_count_line"
    __table_args__ = (
        UniqueConstraint("count_id", "line_no", name="uq_erp_inventory_count_line_no"),
        {**OPTIONS, "comment": "库存盘点明细"},
    )

    count_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_inventory_count.id", ondelete="CASCADE"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_product.id"), nullable=False, index=True)
    unit_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_unit.id"), nullable=False)
    system_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    counted_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    difference_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    snapshot_unit_cost: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    batch_no: Mapped[str | None] = mapped_column(String(80))
    production_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    system_serial_numbers: Mapped[str | None] = mapped_column(Text)
    counted_serial_numbers: Mapped[str | None] = mapped_column(Text)
    remark: Mapped[str | None] = mapped_column(String(500))


class ErpOtherStockOrder(BaseModel):
    """保存不属于采购销售等来源的其他出入库单。"""

    __tablename__ = "erp_other_stock_order"
    __table_args__ = (
        UniqueConstraint("order_no", name="uq_erp_other_stock_order_no"),
        {**OPTIONS, "comment": "其他出入库单"},
    )

    order_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_warehouse.id"), nullable=False)
    employee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_employee.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    total_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(Integer)
    approved_by_id: Mapped[int | None] = mapped_column(Integer)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    posting_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ErpOtherStockOrderLine(BaseModel):
    """保存其他出入库商品、成本、批次和序列号。"""

    __tablename__ = "erp_other_stock_order_line"
    __table_args__ = (
        UniqueConstraint("order_id", "line_no", name="uq_erp_other_stock_order_line_no"),
        {**OPTIONS, "comment": "其他出入库明细"},
    )

    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_other_stock_order.id", ondelete="CASCADE"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_product.id"), nullable=False, index=True)
    unit_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_unit.id"), nullable=False)
    unit_to_base_rate: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    base_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    batch_no: Mapped[str | None] = mapped_column(String(80))
    production_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    serial_numbers: Mapped[str | None] = mapped_column(Text)
    remark: Mapped[str | None] = mapped_column(String(500))
