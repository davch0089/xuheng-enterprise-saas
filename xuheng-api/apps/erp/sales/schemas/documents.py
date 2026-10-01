"""销售订单、出库和退货输入模型。"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


class SalesLineInput(BaseModel):
    """销售订单或出库单的商品行输入。"""

    product_id: int
    warehouse_id: int | None = None
    unit_id: int
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    discount_rate: Decimal = Field(default=Decimal("100"), ge=0, le=100)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    order_line_id: int | None = None
    batch_no: str | None = None
    serial_numbers: list[str] = Field(default_factory=list)
    remark: str | None = None

    @field_validator("warehouse_id", "order_line_id", mode="before")
    @classmethod
    def empty_ids_to_none(cls, value):
        """将前端空字符串 ID 转换为空值。"""

        return None if value in ("", None) else value

    @field_validator("batch_no", mode="before")
    @classmethod
    def empty_batch_to_none(cls, value):
        """将空批次号转换为空值。"""

        return value.strip() if isinstance(value, str) and value.strip() else None

    @field_validator("serial_numbers", mode="before")
    @classmethod
    def normalize_serials(cls, value):
        """清理并去重序列号输入。"""

        if not value:
            return []
        result = []
        for item in value:
            serial = str(item).strip()
            if serial and serial not in result:
                result.append(serial)
        return result


class SalesOrderInput(BaseModel):
    """销售订单表头和商品明细输入。"""

    order_no: str | None = None
    business_date: date
    expected_delivery_date: date | None = None
    customer_id: int
    warehouse_id: int
    employee_id: int | None = None
    delivery_address: str | None = None
    remark: str | None = None
    lines: list[SalesLineInput] = Field(min_length=1)

    @field_validator("order_no", "delivery_address", mode="before")
    @classmethod
    def empty_text_to_none(cls, value):
        """将可选文本中的空字符串转换为空值。"""

        return value.strip() if isinstance(value, str) and value.strip() else None


class SalesDeliveryInput(BaseModel):
    """销售出库单表头和商品明细输入。"""

    delivery_no: str | None = None
    business_date: date
    customer_id: int
    warehouse_id: int
    order_id: int | None = None
    employee_id: int | None = None
    delivery_address: str | None = None
    due_date: date | None = None
    batch_selection_mode: str = Field(default="auto", pattern="^(auto|manual)$")
    settlement_discount_rate: Decimal = Field(default=Decimal("100"), ge=0, le=100)
    rounding_amount: Decimal = Field(default=Decimal("0"), ge=0)
    current_payment_amount: Decimal = Field(default=Decimal("0"), ge=0)
    settlement_method_id: int | None = None
    fund_account_id: int | None = None
    remark: str | None = None
    lines: list[SalesLineInput] = Field(min_length=1)

    @field_validator("order_id", "employee_id", mode="before")
    @classmethod
    def empty_ids_to_none(cls, value):
        """将可选关联 ID 的空字符串转换为空值。"""

        return None if value in ("", None) else value


class SalesReturnLineInput(BaseModel):
    """销售退货单的原出库明细和退货数量输入。"""

    delivery_line_id: int
    quantity: Decimal = Field(gt=0)
    warehouse_id: int | None = None
    unit_id: int | None = None
    batch_no: str | None = None
    serial_numbers: list[str] = Field(default_factory=list)
    remark: str | None = None


class SalesReturnInput(BaseModel):
    """销售退货单表头和退货明细输入。"""

    return_no: str | None = None
    business_date: date
    delivery_id: int
    customer_id: int
    warehouse_id: int
    employee_id: int | None = None
    remark: str | None = None
    lines: list[SalesReturnLineInput] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_delivery_lines(self):
        """确保一张退货单中同一原出库行只出现一次。"""

        ids = [line.delivery_line_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("退货明细不能重复选择同一出库行")
        return self
