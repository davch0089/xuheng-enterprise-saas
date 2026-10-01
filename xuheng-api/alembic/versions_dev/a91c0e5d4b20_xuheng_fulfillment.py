"""Add the Xuheng tenant, product, stock and fulfillment order tables.

Revision ID: a91c0e5d4b20
Revises: e4b8a731c9d2
Create Date: 2026-09-30
"""

from alembic import op
import sqlalchemy as sa


revision = "a91c0e5d4b20"
down_revision = "e4b8a731c9d2"
branch_labels = None
depends_on = None


def _audit():
    return (
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("create_datetime", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("update_datetime", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("delete_datetime", sa.DateTime(), nullable=True),
        sa.Column("is_delete", sa.Boolean(), server_default=sa.text("0"), nullable=False),
    )


def upgrade():
    op.create_table(
        "xh_tenant",
        *_audit(),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.UniqueConstraint("code", name="uq_xh_tenant_code"),
    )
    op.create_table(
        "xh_tenant_member",
        *_audit(),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("xh_tenant.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("vadmin_auth_user.id"), nullable=False),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_xh_tenant_member"),
    )
    op.create_table(
        "xh_product",
        *_audit(),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("xh_tenant.id"), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("sale_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.UniqueConstraint("tenant_id", "code", name="uq_xh_product_code"),
    )
    op.create_table(
        "xh_order",
        *_audit(),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("xh_tenant.id"), nullable=False),
        sa.Column("order_no", sa.String(40), nullable=False),
        sa.Column("customer_name", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("remark", sa.String(200), nullable=True),
        sa.Column("shipped_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("order_no", name="uq_xh_order_no"),
    )
    op.create_table(
        "xh_order_line",
        *_audit(),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("xh_order.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("xh_product.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
    )
    op.create_table(
        "xh_stock",
        *_audit(),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("xh_tenant.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("xh_product.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="0", nullable=False),
        sa.UniqueConstraint("tenant_id", "product_id", name="uq_xh_stock_product"),
    )
    op.create_table(
        "xh_stock_log",
        *_audit(),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("xh_tenant.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("xh_product.id"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("xh_order.id"), nullable=True),
        sa.Column("change_qty", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(20), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
    )
    _install_menus()


def _install_menus():
    menu = sa.table(
        "vadmin_auth_menu",
        sa.column("id", sa.Integer),
        sa.column("title", sa.String),
        sa.column("icon", sa.String),
        sa.column("redirect", sa.String),
        sa.column("component", sa.String),
        sa.column("path", sa.String),
        sa.column("disabled", sa.Boolean),
        sa.column("hidden", sa.Boolean),
        sa.column("order", sa.Integer),
        sa.column("menu_type", sa.String),
        sa.column("parent_id", sa.Integer),
        sa.column("perms", sa.String),
        sa.column("noCache", sa.Boolean),
        sa.column("breadcrumb", sa.Boolean),
        sa.column("affix", sa.Boolean),
        sa.column("noTagsView", sa.Boolean),
        sa.column("canTo", sa.Boolean),
        sa.column("alwaysShow", sa.Boolean),
        sa.column("is_delete", sa.Boolean),
    )
    bind = op.get_bind()
    root_id = bind.execute(menu.insert().values(
        title="序衡", icon="ep:office-building", redirect="/xuheng/tenants", component="#",
        path="/xuheng", disabled=False, hidden=False, order=0, menu_type="0", parent_id=None,
        perms=None, noCache=False, breadcrumb=True, affix=False, noTagsView=False,
        canTo=False, alwaysShow=True, is_delete=False,
    )).lastrowid
    pages = (
        ("企业", "tenants", "views/Xuheng/Tenant", 1),
        ("商品", "products", "views/Xuheng/Product", 2),
        ("订单", "orders", "views/Xuheng/Order", 3),
    )
    for title, path, component, order in pages:
        bind.execute(menu.insert().values(
            title=title, icon=None, redirect=None, component=component, path=path,
            disabled=False, hidden=False, order=order, menu_type="1", parent_id=root_id,
            perms=None, noCache=False, breadcrumb=True, affix=False, noTagsView=False,
            canTo=False, alwaysShow=False, is_delete=False,
        ))


def downgrade():
    op.drop_table("xh_stock_log")
    op.drop_table("xh_stock")
    op.drop_table("xh_order_line")
    op.drop_table("xh_order")
    op.drop_table("xh_product")
    op.drop_table("xh_tenant_member")
    op.drop_table("xh_tenant")
    op.execute("DELETE FROM vadmin_auth_menu WHERE path IN ('/xuheng', 'tenants', 'products', 'orders')")
