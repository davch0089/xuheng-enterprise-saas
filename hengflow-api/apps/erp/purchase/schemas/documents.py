"""采购订单、收货和退货输入模型。"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PurchaseLineInput(BaseModel):
    """采购单据通用商品明细。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    product_id: int
    warehouse_id: int | None = None
    unit_id: int
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(default=0, ge=0)
    tax_rate: Decimal = Field(default=0, ge=0, le=100)
    order_line_id: int | None = None
    receipt_line_id: int | None = None
    batch_no: str | None = Field(default=None, max_length=80)
    production_date: date | None = None
    expiry_date: date | None = None
    serial_numbers: list[str] = Field(default_factory=list)
    remark: str | None = Field(default=None, max_length=500)

    @field_validator("batch_no", "remark", mode="before")
    @classmethod
    def empty_to_none(cls, value):
        """将可选文本空字符串转换为空值。"""

        return value or None

    @field_validator("serial_numbers")
    @classmethod
    def normalize_serials(cls, value):
        """清理并拒绝重复序列号。"""

        values = [str(item).strip() for item in (value or []) if str(item).strip()]
        if len(values) != len(set(values)):
            raise ValueError("同一行序列号不能重复")
        return values


class PurchaseOrderInput(BaseModel):
    """采购订单表头和商品输入。"""

    order_no: str | None = Field(default=None, max_length=50)
    business_date: date
    expected_receipt_date: date | None = None
    supplier_id: int
    warehouse_id: int
    employee_id: int | None = None
    remark: str | None = None
    lines: list[PurchaseLineInput] = Field(min_length=1)


class PurchaseReceiptInput(BaseModel):
    """采购收货表头、订单来源和跟踪属性输入。"""

    receipt_no: str | None = Field(default=None, max_length=50)
    business_date: date
    supplier_id: int
    warehouse_id: int
    employee_id: int | None = None
    order_id: int | None = None
    due_date: date | None = None
    settlement_discount_rate: Decimal = Field(default=Decimal("100"), ge=0, le=100)
    rounding_amount: Decimal = Field(default=Decimal("0"), ge=0)
    current_payment_amount: Decimal = Field(default=Decimal("0"), ge=0)
    settlement_method_id: int | None = None
    fund_account_id: int | None = None
    remark: str | None = None
    lines: list[PurchaseLineInput] = Field(min_length=1)

    @model_validator(mode="after")
    def require_order_lines(self):
        """引用采购订单时要求每行明确对应订单行。"""

        if self.order_id and any(line.order_line_id is None for line in self.lines):
            raise ValueError("订单收货的每一行必须指定采购订单行")
        return self


class PurchaseReturnInput(BaseModel):
    """采购退货表头和原收货明细输入。"""

    return_no: str | None = Field(default=None, max_length=50)
    business_date: date
    receipt_id: int
    supplier_id: int
    warehouse_id: int
    employee_id: int | None = None
    remark: str | None = None
    lines: list[PurchaseLineInput] = Field(min_length=1)

    @model_validator(mode="after")
    def require_receipt_lines(self):
        """采购退货每行必须引用原收货明细。"""

        if any(line.receipt_line_id is None for line in self.lines):
            raise ValueError("采购退货的每一行必须指定原收货行")
        return self
