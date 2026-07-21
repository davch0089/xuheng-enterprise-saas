from decimal import Decimal

from db.db_base import BaseModel
from sqlalchemy import Boolean, DECIMAL, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class ErpProductCategory(BaseModel):
    __tablename__ = "erp_product_category"
    __table_args__ = (UniqueConstraint("code", name="uq_erp_product_category_code"), {"comment": "商品分类", "mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"})

    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="分类编码")
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="分类名称")
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_product_category.id", ondelete="SET NULL"))
    order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    remark: Mapped[str | None] = mapped_column(String(500), comment="备注")


class ErpUnit(BaseModel):
    __tablename__ = "erp_unit"
    __table_args__ = (UniqueConstraint("code", name="uq_erp_unit_code"), {"comment": "计量单位", "mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"})

    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="单位编码")
    name: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="单位名称")
    symbol: Mapped[str | None] = mapped_column(String(20), comment="单位符号")
    decimal_places: Mapped[int] = mapped_column(Integer, default=2, comment="数量小数位")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    remark: Mapped[str | None] = mapped_column(String(500), comment="备注")


class ErpProductSpu(BaseModel):
    """保存商品的公共档案；实际交易、库存与成本仍由下属 SKU 承担。"""

    __tablename__ = "erp_product_spu"
    __table_args__ = (
        UniqueConstraint("code", name="uq_erp_product_spu_code"),
        {"comment": "商品SPU档案", "mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    code: Mapped[str] = mapped_column(String(60), nullable=False, index=True, comment="SPU编码")
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True, comment="商品名称")
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_product_category.id"), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(100), comment="品牌")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    remark: Mapped[str | None] = mapped_column(Text, comment="备注")


class ErpProduct(BaseModel):
    """保存可独立采购、销售、库存和计价的 SKU。"""

    __tablename__ = "erp_product"
    __table_args__ = (
        UniqueConstraint("code", name="uq_erp_product_code"),
        UniqueConstraint("barcode", name="uq_erp_product_barcode"),
        UniqueConstraint("spu_id", "variant_key", name="uq_erp_product_spu_variant"),
        {"comment": "商品资料", "mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    spu_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_product_spu.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(60), nullable=False, index=True, comment="商品编码/SKU")
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True, comment="商品名称")
    barcode: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True, comment="条码")
    variant_name: Mapped[str] = mapped_column(String(200), nullable=False, default="默认规格", comment="SKU规格名称")
    variant_key: Mapped[str] = mapped_column(String(500), nullable=False, comment="规格组合唯一键")
    is_default_sku: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否默认SKU")
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_product_category.id"), nullable=False)
    base_unit_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_unit.id"), nullable=False)
    multi_unit_enabled: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否启用多单位")
    unit_group_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_unit_group.id"), comment="多单位方案")
    specification: Mapped[str | None] = mapped_column(String(150), comment="规格型号")
    brand: Mapped[str | None] = mapped_column(String(100), comment="品牌")
    default_purchase_price: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), default=0, comment="参考进价")
    default_sale_price: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), default=0, comment="参考售价")
    tax_rate: Mapped[Decimal] = mapped_column(DECIMAL(8, 4), default=0, comment="默认税率百分比")
    min_stock: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), default=0, comment="最低库存")
    max_stock: Mapped[Decimal | None] = mapped_column(DECIMAL(18, 4), comment="最高库存")
    costing_method: Mapped[str] = mapped_column(String(30), default="moving_average", comment="成本计价方法")
    batch_enabled: Mapped[bool] = mapped_column(Boolean, default=False, comment="启用批次")
    serial_enabled: Mapped[bool] = mapped_column(Boolean, default=False, comment="启用序列号")
    shelf_life_days: Mapped[int | None] = mapped_column(Integer, comment="保质期天数")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    remark: Mapped[str | None] = mapped_column(Text, comment="备注")


class ErpProductAttribute(BaseModel):
    """定义可复用的 SKU 规格维度，例如颜色、尺寸。"""

    __tablename__ = "erp_product_attribute"
    __table_args__ = (
        UniqueConstraint("name", name="uq_erp_product_attribute_name"),
        {"comment": "SKU属性定义", "mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    name: Mapped[str] = mapped_column(String(80), nullable=False, index=True, comment="属性名称")
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ErpProductAttributeValue(BaseModel):
    """保存一个 SKU 属性维度下可使用的值。"""

    __tablename__ = "erp_product_attribute_value"
    __table_args__ = (
        UniqueConstraint("attribute_id", "value", name="uq_erp_product_attribute_value"),
        {"comment": "SKU属性值", "mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    attribute_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("erp_product_attribute.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="属性值")
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ErpProductSkuAttribute(BaseModel):
    """关联一个 SKU 与其每个规格维度的具体值。"""

    __tablename__ = "erp_product_sku_attribute"
    __table_args__ = (
        UniqueConstraint("product_id", "attribute_id", name="uq_erp_product_sku_attribute"),
        {"comment": "SKU属性组合", "mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("erp_product.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attribute_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("erp_product_attribute.id", ondelete="RESTRICT"), nullable=False
    )
    value_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("erp_product_attribute_value.id", ondelete="RESTRICT"), nullable=False
    )


class ErpUnitGroup(BaseModel):
    __tablename__ = "erp_unit_group"
    __table_args__ = (
        UniqueConstraint("name", name="uq_erp_unit_group_name"),
        {"comment": "多单位方案", "mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="方案名称")
    primary_unit_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_unit.id"), nullable=False, comment="主单位")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    remark: Mapped[str | None] = mapped_column(String(500), comment="备注")


class ErpUnitGroupItem(BaseModel):
    __tablename__ = "erp_unit_group_item"
    __table_args__ = (
        UniqueConstraint("group_id", "unit_id", name="uq_erp_unit_group_item_unit"),
        {"comment": "多单位方案明细", "mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_unit_group.id", ondelete="CASCADE"), nullable=False)
    unit_id: Mapped[int] = mapped_column(Integer, ForeignKey("erp_unit.id"), nullable=False, comment="子单位")
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("erp_unit_group_item.id", ondelete="RESTRICT"), comment="上级明细；为空时上级为主单位"
    )
    factor: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False, comment="1上级单位等于当前单位数量")
    order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")


class ErpSettlementMethod(BaseModel):
    __tablename__ = "erp_settlement_method"
    __table_args__ = (UniqueConstraint("code", name="uq_erp_settlement_method_code"), {"comment": "结算方式", "mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"})

    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="结算编码")
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="结算名称")
    method_type: Mapped[str] = mapped_column(String(30), default="other", comment="结算类型")
    payment_days: Mapped[int] = mapped_column(Integer, default=0, comment="默认账期天数")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    remark: Mapped[str | None] = mapped_column(String(500), comment="备注")


class ErpWarehouse(BaseModel):
    __tablename__ = "erp_warehouse"
    __table_args__ = (UniqueConstraint("code", name="uq_erp_warehouse_code"), {"comment": "仓库资料", "mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"})

    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="仓库编码")
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="仓库名称")
    manager_name: Mapped[str | None] = mapped_column(String(50), comment="负责人")
    phone: Mapped[str | None] = mapped_column(String(30), comment="联系电话")
    address: Mapped[str | None] = mapped_column(String(255), comment="地址")
    allow_negative_stock: Mapped[bool] = mapped_column(Boolean, default=False, comment="允许负库存")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    remark: Mapped[str | None] = mapped_column(String(500), comment="备注")


class PartnerMixin:
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="编码")
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True, comment="名称")
    short_name: Mapped[str | None] = mapped_column(String(80), comment="简称")
    category: Mapped[str | None] = mapped_column(String(50), comment="分类")
    contact_name: Mapped[str | None] = mapped_column(String(50), comment="联系人")
    phone: Mapped[str | None] = mapped_column(String(30), comment="联系电话")
    email: Mapped[str | None] = mapped_column(String(100), comment="邮箱")
    tax_no: Mapped[str | None] = mapped_column(String(50), comment="税号")
    bank_name: Mapped[str | None] = mapped_column(String(100), comment="开户行")
    bank_account: Mapped[str | None] = mapped_column(String(80), comment="银行账号")
    address: Mapped[str | None] = mapped_column(String(255), comment="地址")
    settlement_method_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("erp_settlement_method.id"))
    payment_days: Mapped[int] = mapped_column(Integer, default=0, comment="账期天数")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    remark: Mapped[str | None] = mapped_column(String(500), comment="备注")


class ErpCustomer(PartnerMixin, BaseModel):
    __tablename__ = "erp_customer"
    __table_args__ = (UniqueConstraint("code", name="uq_erp_customer_code"), {"comment": "客户资料", "mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"})

    credit_limit: Mapped[Decimal] = mapped_column(DECIMAL(18, 2), default=0, comment="信用额度")


class ErpSupplier(PartnerMixin, BaseModel):
    __tablename__ = "erp_supplier"
    __table_args__ = (UniqueConstraint("code", name="uq_erp_supplier_code"), {"comment": "供应商资料", "mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"})


class ErpEmployee(BaseModel):
    __tablename__ = "erp_employee"
    __table_args__ = (UniqueConstraint("code", name="uq_erp_employee_code"), {"comment": "职员资料", "mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"})

    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="职员编码")
    name: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="姓名")
    # 上游部门表可能使用 MyISAM，暂不建立跨引擎数据库外键，由应用层维护该引用。
    department_id: Mapped[int | None] = mapped_column(Integer)
    position: Mapped[str | None] = mapped_column(String(80), comment="职位")
    phone: Mapped[str | None] = mapped_column(String(30), comment="联系电话")
    email: Mapped[str | None] = mapped_column(String(100), comment="邮箱")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    remark: Mapped[str | None] = mapped_column(String(500), comment="备注")
