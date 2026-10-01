"""序衡主线接口入参。"""

from decimal import Decimal

from pydantic import BaseModel, Field


class TenantIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=80)


class ProductIn(BaseModel):
    tenant_id: int
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    sale_price: Decimal = Field(ge=0)
    opening_quantity: int = Field(default=0, ge=0)


class StockAdjustIn(BaseModel):
    tenant_id: int
    product_id: int
    quantity: int = Field(gt=0)


class OrderLineIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderIn(BaseModel):
    tenant_id: int
    customer_name: str = Field(min_length=1, max_length=80)
    remark: str | None = Field(default=None, max_length=200)
    lines: list[OrderLineIn] = Field(min_length=1)
