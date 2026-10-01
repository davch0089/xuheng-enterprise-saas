"""库存调拨、盘点和其他出入库输入模型。"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TrackedStockLineInput(BaseModel):
    """库存作业共用的商品、单位及跟踪维度输入。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    product_id: int
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
    def empty_text_to_none(cls, value):
        """将空文本标准化为空值。"""

        return value.strip() if isinstance(value, str) and value.strip() else None

    @field_validator("serial_numbers", mode="before")
    @classmethod
    def normalize_serials(cls, value):
        """清理并校验当前行的序列号列表。"""

        values = [str(item).strip() for item in (value or []) if str(item).strip()]
        if len(values) != len(set(values)):
            raise ValueError("同一明细不能包含重复序列号")
        return values


class StockTransferInput(BaseModel):
    """一步或两步库存调拨单输入。"""

    transfer_no: str | None = Field(default=None, max_length=50)
    transfer_date: date
    transfer_mode: str = Field(pattern="^(one_step|two_step)$")
    source_warehouse_id: int
    destination_warehouse_id: int
    employee_id: int | None = None
    remark: str | None = None
    lines: list[TrackedStockLineInput] = Field(min_length=1)

    @model_validator(mode="after")
    def different_warehouses(self):
        """禁止同仓库调拨。"""

        if self.source_warehouse_id == self.destination_warehouse_id:
            raise ValueError("调出仓库和调入仓库不能相同")
        return self


class InventoryCountLineInput(BaseModel):
    """盘点商品的实盘数量和实盘序列号输入。"""

    product_id: int
    counted_quantity: Decimal = Field(ge=0)
    batch_no: str | None = Field(default=None, max_length=80)
    counted_serial_numbers: list[str] = Field(default_factory=list)
    remark: str | None = Field(default=None, max_length=500)

    @field_validator("counted_serial_numbers", mode="before")
    @classmethod
    def normalize_serials(cls, value):
        """清理实盘序列号并拒绝重复项。"""

        values = [str(item).strip() for item in (value or []) if str(item).strip()]
        if len(values) != len(set(values)):
            raise ValueError("实盘序列号不能重复")
        return values


class InventoryCountInput(BaseModel):
    """库存盘点单表头及实盘明细输入。"""

    count_no: str | None = Field(default=None, max_length=50)
    count_date: date
    warehouse_id: int
    employee_id: int | None = None
    remark: str | None = None
    lines: list[InventoryCountLineInput] = Field(min_length=1)


class OtherStockOrderInput(BaseModel):
    """其他入库或其他出库单输入。"""

    order_no: str | None = Field(default=None, max_length=50)
    business_date: date
    direction: str = Field(pattern="^(inbound|outbound)$")
    reason: str = Field(min_length=1, max_length=100)
    warehouse_id: int
    employee_id: int | None = None
    remark: str | None = None
    lines: list[TrackedStockLineInput] = Field(min_length=1)
