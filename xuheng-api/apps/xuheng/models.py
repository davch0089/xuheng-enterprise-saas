"""序衡主线数据：企业、商品、简单库存和履约订单。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.db_base import BaseModel


class XhTenant(BaseModel):
    """使用序衡的企业。业务数据都挂在企业下。"""

    __tablename__ = "xh_tenant"
    __table_args__ = {"comment": "序衡企业"}

    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class XhTenantMember(BaseModel):
    """用户可进入的企业。"""

    __tablename__ = "xh_tenant_member"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_xh_tenant_member"),
        {"comment": "序衡企业成员"},
    )

    tenant_id: Mapped[int] = mapped_column(ForeignKey("xh_tenant.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("vadmin_auth_user.id"), nullable=False, index=True)


class XhProduct(BaseModel):
    """企业内商品。库存不走批次和成本引擎。"""

    __tablename__ = "xh_product"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_xh_product_code"),
        {"comment": "序衡商品"},
    )

    tenant_id: Mapped[int] = mapped_column(ForeignKey("xh_tenant.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sale_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    stock: Mapped["XhStock | None"] = relationship(back_populates="product", uselist=False)


class XhStock(BaseModel):
    """一个企业下一件商品的当前数量。"""

    __tablename__ = "xh_stock"
    __table_args__ = (
        UniqueConstraint("tenant_id", "product_id", name="uq_xh_stock_product"),
        {"comment": "序衡库存数量"},
    )

    tenant_id: Mapped[int] = mapped_column(ForeignKey("xh_tenant.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("xh_product.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    product: Mapped[XhProduct] = relationship(back_populates="stock")


class XhStockLog(BaseModel):
    """发货、退货和手工调整产生的数量流水。"""

    __tablename__ = "xh_stock_log"
    __table_args__ = {"comment": "序衡库存流水"}

    tenant_id: Mapped[int] = mapped_column(ForeignKey("xh_tenant.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("xh_product.id"), nullable=False, index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("xh_order.id"), nullable=True)
    change_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)


class XhOrder(BaseModel):
    """一张订单走完确认、发货、完成或关闭。"""

    __tablename__ = "xh_order"
    __table_args__ = {"comment": "序衡订单"}

    tenant_id: Mapped[int] = mapped_column(ForeignKey("xh_tenant.id"), nullable=False, index=True)
    order_no: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    customer_name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_confirm", index=True)
    remark: Mapped[str | None] = mapped_column(String(200), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lines: Mapped[list["XhOrderLine"]] = relationship(back_populates="order")


class XhOrderLine(BaseModel):
    """订单商品行。价格在下单时从商品复制。"""

    __tablename__ = "xh_order_line"
    __table_args__ = {"comment": "序衡订单明细"}

    order_id: Mapped[int] = mapped_column(ForeignKey("xh_order.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("xh_product.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    order: Mapped[XhOrder] = relationship(back_populates="lines")
