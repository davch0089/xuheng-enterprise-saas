"""库存数量、批次、序列号和不可变流水实体。"""

from datetime import date, datetime
from decimal import Decimal

from db.db_base import BaseModel
from sqlalchemy import DECIMAL, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column


MYSQL_OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


class ErpInventoryBalance(BaseModel):
    """仓库商品维度的库存数量余额。"""

    __tablename__ = "erp_inventory_balance"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "product_id", name="uq_erp_inventory_balance"),
        {**MYSQL_OPTIONS, "comment": "库存余额"},
    )

    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_warehouse.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_product.id"), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    available_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    reserved_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0, comment="已预留数量")
    frozen_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0, comment="冻结数量")
    average_cost: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    inventory_value: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    last_movement_at: Mapped[datetime | None] = mapped_column(DateTime)


class ErpInventoryLedger(BaseModel):
    """记录不可变的库存数量收发流水。"""

    __tablename__ = "erp_inventory_ledger"
    __table_args__ = (
        UniqueConstraint("movement_no", name="uq_erp_inventory_ledger_movement_no"),
        UniqueConstraint("idempotency_key", name="uq_erp_inventory_ledger_idempotency_key"),
        {**MYSQL_OPTIONS, "comment": "库存收发流水"},
    )

    movement_no: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False, index=True, comment="过账幂等键")
    movement_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True, comment="统一库存移动类型")
    business_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    business_no: Mapped[str | None] = mapped_column(String(60), index=True, comment="业务单号快照")
    business_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    business_line_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    movement_role: Mapped[str] = mapped_column(String(30), nullable=False, default="main", comment="同一业务行的移动角色")
    posting_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reversal_of_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("erp_inventory_ledger.id", ondelete="RESTRICT"), index=True, comment="被冲销的原流水"
    )
    direction: Mapped[int] = mapped_column(Integer, nullable=False, comment="1收入，-1发出")
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_warehouse.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_product.id"), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, comment="主单位变动数量")
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, comment="成本变动额")
    balance_quantity_before: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    balance_quantity_after: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    average_cost_before: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    average_cost_after: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    batch_no: Mapped[str | None] = mapped_column(String(80), comment="批次快照")
    production_date: Mapped[date | None] = mapped_column(Date, comment="生产日期快照")
    expiry_date: Mapped[date | None] = mapped_column(Date, comment="有效期快照")
    serial_numbers: Mapped[str | None] = mapped_column(Text, comment="序列号快照JSON")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    operator_id: Mapped[int | None] = mapped_column(Integer)
class ErpInventoryBatchBalance(BaseModel):
    """仓库商品批次维度的库存余额。"""

    __tablename__ = "erp_inventory_batch_balance"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "product_id", "batch_no", name="uq_erp_inventory_batch_balance"),
        {**MYSQL_OPTIONS, "comment": "批次库存余额"},
    )

    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_warehouse.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_product.id"), nullable=False)
    batch_no: Mapped[str] = mapped_column(String(80), nullable=False)
    production_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    reserved_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0, comment="已预留数量")
    frozen_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0, comment="冻结数量")


class ErpInventorySerial(BaseModel):
    """记录单件序列号的仓库位置和库存状态。"""

    __tablename__ = "erp_inventory_serial"
    __table_args__ = (
        UniqueConstraint("product_id", "serial_no", name="uq_erp_inventory_serial"),
        {**MYSQL_OPTIONS, "comment": "序列号库存"},
    )

    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_product.id"), nullable=False, index=True)
    serial_no: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    warehouse_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_warehouse.id"), nullable=True)
    batch_no: Mapped[str | None] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_stock")
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True, comment="首次入库来源类型")
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="首次入库来源ID")
    source_line_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="首次入库来源行ID")
    inbound_receipt_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_inbound_receipt.id"))
    inbound_line_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_inbound_receipt_line.id"))
    inbound_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_movement_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("erp_inventory_ledger.id", ondelete="RESTRICT"), comment="最后库存流水"
    )


class ErpInventorySerialMovement(BaseModel):
    """记录序列号每次入库、出库、调拨、退货和冲销状态变化。"""

    __tablename__ = "erp_inventory_serial_movement"
    __table_args__ = (
        UniqueConstraint("serial_id", "stock_movement_id", name="uq_erp_serial_movement"),
        {**MYSQL_OPTIONS, "comment": "序列号生命周期流水"},
    )

    serial_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_inventory_serial.id", ondelete="RESTRICT"), nullable=False, index=True)
    stock_movement_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_inventory_ledger.id", ondelete="RESTRICT"), nullable=False, index=True)
    serial_no: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_no: Mapped[str | None] = mapped_column(String(60))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    from_warehouse_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_warehouse.id"))
    to_warehouse_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_warehouse.id"))
    from_batch_no: Mapped[str | None] = mapped_column(String(80))
    to_batch_no: Mapped[str | None] = mapped_column(String(80))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    operator_id: Mapped[int | None] = mapped_column(Integer)
@event.listens_for(ErpInventoryLedger, "before_update")
def prevent_inventory_ledger_update(*_):
    """拒绝修改已落库的库存流水。"""

    raise RuntimeError("库存流水不可修改；请通过冲销流水更正")


@event.listens_for(ErpInventoryLedger, "before_delete")
def prevent_inventory_ledger_delete(*_):
    """拒绝删除已落库的库存流水。"""

    raise RuntimeError("库存流水不可删除；请通过冲销流水更正")
