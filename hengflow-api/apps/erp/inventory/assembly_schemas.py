"""BOM与组装拆卸输入模型。"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


class BomLineInput(BaseModel):
    """BOM子件用量输入。"""

    component_product_id: int
    unit_id: int
    quantity: Decimal = Field(gt=0)
    loss_rate: Decimal = Field(default=0, ge=0, le=100)
    remark: str | None = None


class BomInput(BaseModel):
    """简化BOM表头和子件输入。"""

    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=120)
    product_id: int
    unit_id: int
    output_quantity: Decimal = Field(default=1, gt=0)
    version: str = Field(default="1.0", max_length=30)
    is_active: bool = True
    remark: str | None = None
    lines: list[BomLineInput] = Field(min_length=1)

    @model_validator(mode="after")
    def no_finished_as_component(self):
        """禁止成品自身作为直接子件并拒绝重复子件。"""

        ids = [x.component_product_id for x in self.lines]
        if self.product_id in ids:
            raise ValueError("成品不能作为自身子件")
        if len(ids) != len(set(ids)):
            raise ValueError("BOM子件不能重复")
        return self


class AssemblyTrackingInput(BaseModel):
    """工单商品的批次和序列号输入。"""

    product_id: int
    batch_no: str | None = None
    production_date: date | None = None
    expiry_date: date | None = None
    serial_numbers: list[str] = Field(default_factory=list)

    @field_validator("serial_numbers", mode="before")
    @classmethod
    def normalize_serials(cls, value):
        """清理并拒绝重复序列号。"""

        values = [str(x).strip() for x in (value or []) if str(x).strip()]
        if len(values) != len(set(values)):
            raise ValueError("序列号不能重复")
        return values


class AssemblyOrderInput(BaseModel):
    """组装或拆卸工单输入。"""

    order_no: str | None = Field(default=None, max_length=50)
    business_date: date
    order_type: str = Field(pattern="^(assembly|disassembly)$")
    bom_id: int
    warehouse_id: int
    employee_id: int | None = None
    quantity: Decimal = Field(gt=0)
    tracking: list[AssemblyTrackingInput] = Field(default_factory=list)
    remark: str | None = None
