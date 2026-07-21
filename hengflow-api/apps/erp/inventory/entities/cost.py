"""独立成本余额和不可变成本流水实体。"""

from datetime import datetime
from decimal import Decimal

from db.db_base import BaseModel
from sqlalchemy import Boolean, DECIMAL, DateTime, ForeignKey, Integer, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column


MYSQL_OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


class ErpInventoryCostBalance(BaseModel):
    """仓库商品维度的独立成本数量、价值和平均价余额。"""

    __tablename__ = "erp_inventory_cost_balance"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "product_id", name="uq_erp_inventory_cost_balance"),
        {**MYSQL_OPTIONS, "comment": "库存成本余额"},
    )

    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("erp_warehouse.id"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("erp_product.id"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    inventory_value: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    average_cost: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0)
    last_cost_ledger_id: Mapped[int | None] = mapped_column(Integer, comment="最后成本流水ID")
    needs_revaluation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="负库存暂估成本待重算"
    )
    last_cost_at: Mapped[datetime | None] = mapped_column(DateTime)


class ErpInventoryCostLedger(BaseModel):
    """记录不可变的成本变动和计价快照。"""

    __tablename__ = "erp_inventory_cost_ledger"
    __table_args__ = (
        UniqueConstraint("cost_no", name="uq_erp_inventory_cost_ledger_no"),
        UniqueConstraint("idempotency_key", name="uq_erp_inventory_cost_ledger_idempotency_key"),
        UniqueConstraint("stock_movement_id", name="uq_erp_inventory_cost_ledger_stock_movement"),
        {**MYSQL_OPTIONS, "comment": "不可变库存成本流水"},
    )

    cost_no: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    cost_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_no: Mapped[str | None] = mapped_column(String(60), index=True)
    source_line_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_role: Mapped[str] = mapped_column(String(30), nullable=False, default="main")
    posting_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    stock_movement_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("erp_inventory_ledger.id", ondelete="RESTRICT"), index=True
    )
    reversal_of_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("erp_inventory_cost_ledger.id", ondelete="RESTRICT"),
        index=True,
        comment="被冲销的原成本流水",
    )
    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("erp_warehouse.id"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("erp_product.id"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    balance_quantity_before: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    balance_quantity_after: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    balance_value_before: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    balance_value_after: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    average_cost_before: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    average_cost_after: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    provisional: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否使用负库存暂估成本"
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    operator_id: Mapped[int | None] = mapped_column(Integer)
    remark: Mapped[str | None] = mapped_column(String(500))
@event.listens_for(ErpInventoryCostLedger, "before_update")
def prevent_inventory_cost_ledger_update(*_):
    """拒绝修改已落库的成本流水。"""

    raise RuntimeError("成本流水不可修改；请通过冲销或重新计价更正")


@event.listens_for(ErpInventoryCostLedger, "before_delete")
def prevent_inventory_cost_ledger_delete(*_):
    """拒绝删除已落库的成本流水。"""

    raise RuntimeError("成本流水不可删除；请通过冲销或重新计价更正")
