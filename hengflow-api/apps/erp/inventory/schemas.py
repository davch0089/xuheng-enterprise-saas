from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class InboundLineInput(BaseModel):
    """入库单商品明细输入模型。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    product_id: int
    warehouse_id: int | None = None
    unit_id: int
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(default=0, ge=0)
    batch_no: str | None = Field(default=None, max_length=80)
    production_date: date | None = None
    expiry_date: date | None = None
    serial_numbers: list[str] = Field(default_factory=list)
    remark: str | None = Field(default=None, max_length=500)

    @field_validator("batch_no", "remark", mode="before")
    @classmethod
    def empty_string_to_none(cls, value):
        """将日期和批次字段中的空字符串转换为空值。"""

        return value or None

    @field_validator("serial_numbers")
    @classmethod
    def normalize_serials(cls, value):
        """清理序列号空白并去除当前明细内的重复项。"""

        result = [item.strip() for item in value if item and item.strip()]
        if len(result) != len(set(result)):
            raise ValueError("同一行不能录入重复序列号")
        return result


class InboundReceiptInput(BaseModel):
    """入库单表头和明细输入模型。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    receipt_no: str | None = Field(default=None, max_length=40)
    receipt_date: date
    business_type: str = Field(default="other", pattern="^(purchase|other|stock_gain|production|transfer)$")
    supplier_id: int | None = None
    warehouse_id: int
    employee_id: int | None = None
    remark: str | None = None
    lines: list[InboundLineInput] = Field(min_length=1)

    @field_validator("receipt_no", "remark", mode="before")
    @classmethod
    def empty_string_to_none(cls, value):
        """将可选基础资料字段中的空字符串转换为空值。"""

        return value or None

    @model_validator(mode="after")
    def validate_supplier(self):
        """校验采购入库必须选择供应商。"""

        if self.business_type == "purchase" and self.supplier_id is None:
            raise ValueError("采购入库必须选择供应商")
        return self
