"""ERP 文档中心请求与响应模型。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PrintTemplateInput(BaseModel):
    """校验打印模板新增和修改数据。"""

    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=120)
    business_type: str = Field(min_length=1, max_length=60)
    content_html: str = Field(min_length=1)
    style_css: str | None = None
    sample_data: dict | None = None
    paper_size: Literal["A4", "A5", "Letter"] = "A4"
    orientation: Literal["portrait", "landscape"] = "portrait"
    margin_mm: int = Field(default=10, ge=0, le=50)
    is_default: bool = False
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=500)


class PrintRenderInput(BaseModel):
    """校验打印模板渲染上下文。"""

    template_id: int | None = None
    business_type: str | None = None
    data: dict = Field(default_factory=dict)


class PrintTemplateOut(PrintTemplateInput):
    """序列化打印模板。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int


class AttachmentOut(BaseModel):
    """序列化业务附件元数据。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    business_type: str
    business_id: int
    file_name: str
    file_ext: str | None
    mime_type: str | None
    file_size: int
    storage_type: str
    file_url: str | None
    checksum: str | None
    description: str | None
    uploaded_by_id: int | None
    uploaded_by_name: str | None
    create_datetime: object


class ExchangeTaskOut(BaseModel):
    """序列化数据交换任务。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_type: str
    resource: str
    file_name: str | None
    status: str
    total_count: int
    success_count: int
    failure_count: int
    error_details: list | None
    operator_name: str | None
    create_datetime: object
