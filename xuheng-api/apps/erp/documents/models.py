"""ERP 文档中心 ORM 实体。"""

from db.db_base import BaseModel
from sqlalchemy import BigInteger, Boolean, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


class ErpAttachment(BaseModel):
    """保存任意 ERP 业务对象关联的附件元数据。"""

    __tablename__ = "erp_attachment"
    __table_args__ = ({**OPTIONS, "comment": "ERP业务附件"},)

    business_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    business_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_ext: Mapped[str | None] = mapped_column(String(30))
    mime_type: Mapped[str | None] = mapped_column(String(150))
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    storage_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_url: Mapped[str | None] = mapped_column(String(1000))
    checksum: Mapped[str | None] = mapped_column(String(64), index=True)
    description: Mapped[str | None] = mapped_column(String(500))
    uploaded_by_id: Mapped[int | None] = mapped_column(Integer, index=True)
    uploaded_by_name: Mapped[str | None] = mapped_column(String(100))


class ErpPrintTemplate(BaseModel):
    """保存按业务类型配置的 HTML 打印模板。"""

    __tablename__ = "erp_print_template"
    __table_args__ = (
        UniqueConstraint("code", name="uq_erp_print_template_code"),
        {**OPTIONS, "comment": "ERP打印模板"},
    )

    code: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    business_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    content_html: Mapped[str] = mapped_column(Text, nullable=False)
    style_css: Mapped[str | None] = mapped_column(Text)
    sample_data: Mapped[dict | None] = mapped_column(JSON)
    paper_size: Mapped[str] = mapped_column(String(20), nullable=False, default="A4")
    orientation: Mapped[str] = mapped_column(String(20), nullable=False, default="portrait")
    margin_mm: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    remark: Mapped[str | None] = mapped_column(String(500))


class ErpDataExchangeTask(BaseModel):
    """记录一次 Excel 导入或导出任务及处理结果。"""

    __tablename__ = "erp_data_exchange_task"
    __table_args__ = ({**OPTIONS, "comment": "ERP数据导入导出任务"},)

    task_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    file_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processing", index=True)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_details: Mapped[list | None] = mapped_column(JSON)
    operator_id: Mapped[int | None] = mapped_column(Integer, index=True)
    operator_name: Mapped[str | None] = mapped_column(String(100))
