"""简化BOM及组装拆卸工单实体。"""

from datetime import date, datetime
from decimal import Decimal

from db.db_base import BaseModel
from sqlalchemy import Boolean, DECIMAL, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


class ErpBillOfMaterial(BaseModel):
    """定义一个成品及其单位产出的子件用量。"""

    __tablename__ = "erp_bill_of_material"
    __table_args__ = (
        UniqueConstraint("code", name="uq_erp_bom_code"),
        UniqueConstraint("product_id", "version", name="uq_erp_bom_product_version"),
        {**OPTIONS, "comment": "简化物料清单"},
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_product.id"), nullable=False, index=True)
    unit_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_unit.id"), nullable=False)
    output_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=1)
    version: Mapped[str] = mapped_column(String(30), nullable=False, default="1.0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remark: Mapped[str | None] = mapped_column(Text)


class ErpBillOfMaterialLine(BaseModel):
    """定义BOM子件单位用量和损耗率。"""

    __tablename__ = "erp_bill_of_material_line"
    __table_args__ = (
        UniqueConstraint("bom_id", "component_product_id", name="uq_erp_bom_component"),
        {**OPTIONS, "comment": "BOM子件"},
    )

    bom_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_bill_of_material.id", ondelete="CASCADE"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    component_product_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_product.id"), nullable=False, index=True)
    unit_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_unit.id"), nullable=False)
    unit_to_base_rate: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    base_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    loss_rate: Mapped[Decimal] = mapped_column(DECIMAL(10, 4), nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(String(500))


class ErpAssemblyOrder(BaseModel):
    """保存组装或拆卸工单及成本归集结果。"""

    __tablename__ = "erp_assembly_order"
    __table_args__ = (
        UniqueConstraint("order_no", name="uq_erp_assembly_order_no"),
        {**OPTIONS, "comment": "组装拆卸工单"},
    )

    order_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    bom_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_bill_of_material.id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_warehouse.id"), nullable=False)
    employee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_employee.id"))
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    total_component_cost: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    finished_cost: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(Integer)
    approved_by_id: Mapped[int | None] = mapped_column(Integer)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    posting_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ErpAssemblyOrderLine(BaseModel):
    """保存工单成品和子件的数量、跟踪维度与实际成本快照。"""

    __tablename__ = "erp_assembly_order_line"
    __table_args__ = (
        UniqueConstraint("order_id", "line_no", name="uq_erp_assembly_order_line_no"),
        {**OPTIONS, "comment": "组装拆卸工单明细"},
    )

    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_assembly_order.id", ondelete="CASCADE"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    line_role: Mapped[str] = mapped_column(String(20), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_product.id"), nullable=False, index=True)
    unit_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_unit.id"), nullable=False)
    unit_to_base_rate: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    base_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    actual_cost: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0)
    batch_no: Mapped[str | None] = mapped_column(String(80))
    production_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    serial_numbers: Mapped[str | None] = mapped_column(Text)
    remark: Mapped[str | None] = mapped_column(String(500))
