"""入库单据 ORM 实体。"""

from datetime import date, datetime
from decimal import Decimal

from db.db_base import BaseModel
from sqlalchemy import DECIMAL, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


MYSQL_OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


class ErpDocumentSequence(BaseModel):
    """按单据类型和业务日期维护原子编号序列。"""

    __tablename__ = "erp_document_sequence"
    __table_args__ = (
        UniqueConstraint("document_type", "business_date", name="uq_erp_document_sequence"),
        {**MYSQL_OPTIONS, "comment": "ERP单据编号序列"},
    )

    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    current_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ErpInboundReceipt(BaseModel):
    """保存入库单表头、状态和过账版本。"""

    __tablename__ = "erp_inbound_receipt"
    __table_args__ = (
        UniqueConstraint("receipt_no", name="uq_erp_inbound_receipt_no"),
        {**MYSQL_OPTIONS, "comment": "入库单"},
    )

    receipt_no: Mapped[str] = mapped_column(String(40), nullable=False, index=True, comment="入库单号")
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="业务日期")
    business_type: Mapped[str] = mapped_column(String(30), nullable=False, default="other", comment="业务类型")
    supplier_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_supplier.id"), comment="供应商")
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_warehouse.id"), nullable=False, comment="默认仓库")
    employee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_employee.id"), comment="经办人")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True, comment="状态")
    total_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0, comment="主单位总数量")
    total_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0, comment="总成本")
    remark: Mapped[str | None] = mapped_column(Text, comment="备注")
    created_by_id: Mapped[int | None] = mapped_column(Integer, comment="制单人")
    approved_by_id: Mapped[int | None] = mapped_column(Integer, comment="审核人")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, comment="审核时间")
    posting_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="过账批次")


class ErpInboundReceiptLine(BaseModel):
    """保存入库商品、单位换算、批次和序列号快照。"""

    __tablename__ = "erp_inbound_receipt_line"
    __table_args__ = (
        UniqueConstraint("receipt_id", "line_no", name="uq_erp_inbound_receipt_line_no"),
        {**MYSQL_OPTIONS, "comment": "入库单明细"},
    )

    receipt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("erp_inbound_receipt.id", ondelete="CASCADE"), nullable=False, index=True
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_product.id"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_warehouse.id"), nullable=False)
    unit_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_unit.id"), nullable=False)
    unit_to_base_rate: Mapped[Decimal] = mapped_column(
        DECIMAL(20, 8), nullable=False, comment="1录入单位折合主单位数量"
    )
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, comment="录入数量")
    base_quantity: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, comment="主单位数量")
    unit_price: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0, comment="录入单位成本")
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False, default=0, comment="成本金额")
    base_unit_cost: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False, default=0, comment="主单位成本")
    batch_no: Mapped[str | None] = mapped_column(String(80), comment="批次号")
    production_date: Mapped[date | None] = mapped_column(Date, comment="生产日期")
    expiry_date: Mapped[date | None] = mapped_column(Date, comment="有效期至")
    serial_numbers: Mapped[str | None] = mapped_column(Text, comment="序列号JSON")
    remark: Mapped[str | None] = mapped_column(String(500), comment="行备注")
