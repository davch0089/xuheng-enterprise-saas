from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MasterSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_default=True)


class CodedSchema(MasterSchema):
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=150)
    is_active: bool = True
    remark: str | None = None


class ProductCategory(CodedSchema):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    parent_id: int | None = None
    order: int = 0


class Unit(CodedSchema):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=50)
    symbol: str | None = Field(default=None, max_length=20)
    decimal_places: int = Field(default=2, ge=0, le=8)


class Product(CodedSchema):
    spu_id: int
    code: str = Field(min_length=1, max_length=60)
    barcode: str | None = Field(default=None, max_length=80)
    variant_name: str = Field(default="默认规格", min_length=1, max_length=200)
    variant_key: str = Field(default="__DEFAULT__", min_length=1, max_length=500)
    is_default_sku: bool = False
    category_id: int
    base_unit_id: int | None = None
    multi_unit_enabled: bool = False
    unit_group_id: int | None = None
    specification: str | None = None
    brand: str | None = None
    default_purchase_price: Decimal = Field(default=0, ge=0)
    default_sale_price: Decimal = Field(default=0, ge=0)
    tax_rate: Decimal = Field(default=0, ge=0, le=100)
    min_stock: Decimal = Field(default=0, ge=0)
    max_stock: Decimal | None = Field(default=None, ge=0)
    costing_method: str = "moving_average"
    batch_enabled: bool = False
    serial_enabled: bool = False
    shelf_life_days: int | None = Field(default=None, ge=0)

    @field_validator("barcode", mode="before")
    @classmethod
    def empty_barcode_to_none(cls, value):
        return value or None


class ProductSkuAttributeInput(MasterSchema):
    """描述一个 SKU 的规格维度和值。"""

    name: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=100)


class ProductSkuInput(MasterSchema):
    """创建或修改一个可独立核算的 SKU。"""

    id: int | None = None
    code: str = Field(min_length=1, max_length=60)
    barcode: str | None = Field(default=None, max_length=80)
    variant_name: str | None = Field(default=None, max_length=200)
    attributes: list[ProductSkuAttributeInput] = Field(default_factory=list)
    base_unit_id: int | None = None
    multi_unit_enabled: bool = False
    unit_group_id: int | None = None
    specification: str | None = Field(default=None, max_length=150)
    default_purchase_price: Decimal = Field(default=0, ge=0)
    default_sale_price: Decimal = Field(default=0, ge=0)
    tax_rate: Decimal = Field(default=0, ge=0, le=100)
    min_stock: Decimal = Field(default=0, ge=0)
    max_stock: Decimal | None = Field(default=None, ge=0)
    costing_method: str = "moving_average"
    batch_enabled: bool = False
    serial_enabled: bool = False
    shelf_life_days: int | None = Field(default=None, ge=0)
    is_default_sku: bool = False
    is_active: bool = True
    remark: str | None = None

    @field_validator("barcode", mode="before")
    @classmethod
    def normalize_barcode(cls, value):
        """把空条码转成 NULL，使数据库唯一约束允许多个无条码 SKU。"""

        return value or None

    @model_validator(mode="after")
    def validate_attributes(self):
        """保证同一个 SKU 中每个规格维度只出现一次。"""

        names = [item.name.casefold() for item in self.attributes]
        if len(names) != len(set(names)):
            raise ValueError("同一个 SKU 不能重复设置相同属性")
        return self


class ProductSpuInput(MasterSchema):
    """一次保存商品公共档案及其全部 SKU。"""

    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=150)
    category_id: int
    brand: str | None = Field(default=None, max_length=100)
    is_active: bool = True
    remark: str | None = None
    skus: list[ProductSkuInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_skus(self):
        """保证请求内 SKU 编码、条码、规格组合和默认项不冲突。"""

        codes = [item.code.casefold() for item in self.skus]
        barcodes = [item.barcode.casefold() for item in self.skus if item.barcode]
        if len(codes) != len(set(codes)):
            raise ValueError("同一商品下的 SKU 编码不能重复")
        if len(barcodes) != len(set(barcodes)):
            raise ValueError("同一商品下的 SKU 条码不能重复")
        if sum(1 for item in self.skus if item.is_default_sku) > 1:
            raise ValueError("一个商品最多只能设置一个默认 SKU")
        return self


class UnitGroup(MasterSchema):
    name: str = Field(min_length=1, max_length=100)
    primary_unit_id: int
    is_active: bool = True
    remark: str | None = None


class UnitGroupItem(MasterSchema):
    group_id: int
    unit_id: int
    parent_id: int | None = None
    factor: Decimal = Field(gt=0)
    order: int = Field(default=0, ge=0)


class SettlementMethod(CodedSchema):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    method_type: str = "other"
    payment_days: int = Field(default=0, ge=0)


class Warehouse(CodedSchema):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    manager_name: str | None = None
    phone: str | None = None
    address: str | None = None
    allow_negative_stock: bool = False


class Partner(CodedSchema):
    code: str = Field(min_length=1, max_length=50)
    short_name: str | None = None
    category: str | None = None
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None
    tax_no: str | None = None
    bank_name: str | None = None
    bank_account: str | None = None
    address: str | None = None
    settlement_method_id: int | None = None
    payment_days: int = Field(default=0, ge=0)


class Customer(Partner):
    credit_limit: Decimal = Field(default=0, ge=0)


class Supplier(Partner):
    pass


class Employee(CodedSchema):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=50)
    department_id: int | None = None
    position: str | None = None
    phone: str | None = None
    email: str | None = None


class MasterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
