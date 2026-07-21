"""ERP master data

Revision ID: 9c1f2a7e4b11
Revises: 4d6fc36b8a49
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa


revision = "9c1f2a7e4b11"
down_revision = "4d6fc36b8a49"
branch_labels = None
depends_on = None


def base_columns():
    return [
        sa.Column("id", sa.Integer(), primary_key=True, comment="主键ID"),
        sa.Column("create_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("update_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("delete_datetime", sa.DateTime(), nullable=True),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.false()),
    ]


def status_columns():
    return [
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.String(500), nullable=True),
    ]


def coded_columns(name_length=100, code_length=50):
    return [
        sa.Column("code", sa.String(code_length), nullable=False),
        sa.Column("name", sa.String(name_length), nullable=False),
    ]


def upgrade():
    op.create_table(
        "erp_product_category",
        *coded_columns(),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        *status_columns(), *base_columns(),
        sa.ForeignKeyConstraint(["parent_id"], ["erp_product_category.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("code", name="uq_erp_product_category_code"),
        comment="商品分类", mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_table(
        "erp_unit", *coded_columns(50),
        sa.Column("symbol", sa.String(20)),
        sa.Column("decimal_places", sa.Integer(), nullable=False, server_default="2"),
        *status_columns(), *base_columns(),
        sa.UniqueConstraint("code", name="uq_erp_unit_code"), comment="计量单位", mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_table(
        "erp_settlement_method", *coded_columns(),
        sa.Column("method_type", sa.String(30), nullable=False, server_default="other"),
        sa.Column("payment_days", sa.Integer(), nullable=False, server_default="0"),
        *status_columns(), *base_columns(),
        sa.UniqueConstraint("code", name="uq_erp_settlement_method_code"), comment="结算方式", mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_table(
        "erp_warehouse", *coded_columns(),
        sa.Column("manager_name", sa.String(50)), sa.Column("phone", sa.String(30)),
        sa.Column("address", sa.String(255)),
        sa.Column("allow_negative_stock", sa.Boolean(), nullable=False, server_default=sa.false()),
        *status_columns(), *base_columns(),
        sa.UniqueConstraint("code", name="uq_erp_warehouse_code"), comment="仓库资料", mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_table(
        "erp_employee", *coded_columns(50),
        sa.Column("department_id", sa.Integer()), sa.Column("position", sa.String(80)),
        sa.Column("phone", sa.String(30)), sa.Column("email", sa.String(100)),
        *status_columns(), *base_columns(),
        sa.UniqueConstraint("code", name="uq_erp_employee_code"), comment="职员资料", mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_table(
        "erp_product", *coded_columns(150, 60),
        sa.Column("barcode", sa.String(80)), sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("base_unit_id", sa.Integer(), nullable=False), sa.Column("specification", sa.String(150)),
        sa.Column("brand", sa.String(100)),
        sa.Column("default_purchase_price", sa.DECIMAL(18, 4), nullable=False, server_default="0"),
        sa.Column("default_sale_price", sa.DECIMAL(18, 4), nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.DECIMAL(8, 4), nullable=False, server_default="0"),
        sa.Column("min_stock", sa.DECIMAL(18, 4), nullable=False, server_default="0"),
        sa.Column("max_stock", sa.DECIMAL(18, 4)),
        sa.Column("costing_method", sa.String(30), nullable=False, server_default="moving_average"),
        sa.Column("batch_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("serial_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("shelf_life_days", sa.Integer()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.Text()), *base_columns(),
        sa.ForeignKeyConstraint(["category_id"], ["erp_product_category.id"]),
        sa.ForeignKeyConstraint(["base_unit_id"], ["erp_unit.id"]),
        sa.UniqueConstraint("code", name="uq_erp_product_code"),
        sa.UniqueConstraint("barcode", name="uq_erp_product_barcode"), comment="商品资料", mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_table(
        "erp_unit_conversion",
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("from_unit_id", sa.Integer(), nullable=False),
        sa.Column("to_unit_id", sa.Integer(), nullable=False),
        sa.Column("factor", sa.DECIMAL(20, 8), nullable=False),
        *status_columns(), *base_columns(),
        sa.ForeignKeyConstraint(["product_id"], ["erp_product.id"]),
        sa.ForeignKeyConstraint(["from_unit_id"], ["erp_unit.id"]),
        sa.ForeignKeyConstraint(["to_unit_id"], ["erp_unit.id"]),
        sa.UniqueConstraint("product_id", "from_unit_id", "to_unit_id", name="uq_erp_unit_conversion"),
        comment="商品单位换算", mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    partner_columns = [
        *coded_columns(150), sa.Column("short_name", sa.String(80)), sa.Column("category", sa.String(50)),
        sa.Column("contact_name", sa.String(50)), sa.Column("phone", sa.String(30)),
        sa.Column("email", sa.String(100)), sa.Column("tax_no", sa.String(50)),
        sa.Column("bank_name", sa.String(100)), sa.Column("bank_account", sa.String(80)),
        sa.Column("address", sa.String(255)), sa.Column("settlement_method_id", sa.Integer()),
        sa.Column("payment_days", sa.Integer(), nullable=False, server_default="0"),
    ]
    op.create_table(
        "erp_customer", *partner_columns,
        sa.Column("credit_limit", sa.DECIMAL(18, 2), nullable=False, server_default="0"),
        *status_columns(), *base_columns(),
        sa.ForeignKeyConstraint(["settlement_method_id"], ["erp_settlement_method.id"]),
        sa.UniqueConstraint("code", name="uq_erp_customer_code"), comment="客户资料", mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    # Columns cannot be shared between two Table objects; recreate the supplier set.
    supplier_columns = [
        *coded_columns(150), sa.Column("short_name", sa.String(80)), sa.Column("category", sa.String(50)),
        sa.Column("contact_name", sa.String(50)), sa.Column("phone", sa.String(30)),
        sa.Column("email", sa.String(100)), sa.Column("tax_no", sa.String(50)),
        sa.Column("bank_name", sa.String(100)), sa.Column("bank_account", sa.String(80)),
        sa.Column("address", sa.String(255)), sa.Column("settlement_method_id", sa.Integer()),
        sa.Column("payment_days", sa.Integer(), nullable=False, server_default="0"),
    ]
    op.create_table(
        "erp_supplier", *supplier_columns, *status_columns(), *base_columns(),
        sa.ForeignKeyConstraint(["settlement_method_id"], ["erp_settlement_method.id"]),
        sa.UniqueConstraint("code", name="uq_erp_supplier_code"), comment="供应商资料", mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    _insert_menus()


def _insert_menus():
    menu = sa.table(
        "vadmin_auth_menu",
        sa.column("title", sa.String), sa.column("icon", sa.String), sa.column("redirect", sa.String),
        sa.column("component", sa.String), sa.column("path", sa.String), sa.column("disabled", sa.Boolean),
        sa.column("hidden", sa.Boolean), sa.column("order", sa.Integer), sa.column("menu_type", sa.String),
        sa.column("parent_id", sa.Integer), sa.column("perms", sa.String), sa.column("noCache", sa.Boolean),
        sa.column("breadcrumb", sa.Boolean), sa.column("affix", sa.Boolean), sa.column("noTagsView", sa.Boolean),
        sa.column("canTo", sa.Boolean), sa.column("alwaysShow", sa.Boolean), sa.column("is_delete", sa.Boolean),
    )
    bind = op.get_bind()

    def add(title, path=None, component=None, parent_id=None, menu_type="1", order=0, perms=None, icon=None, redirect=None):
        result = bind.execute(menu.insert().values(
            title=title, icon=icon, redirect=redirect, component=component, path=path,
            disabled=False, hidden=False, order=order, menu_type=menu_type, parent_id=parent_id,
            perms=perms, noCache=False, breadcrumb=True, affix=False, noTagsView=False,
            canTo=False, alwaysShow=menu_type == "0", is_delete=False,
        ))
        return result.lastrowid

    root = add("ERP管理", "/erp", "#", menu_type="0", order=20, icon="ep:management", redirect="/erp/products")
    pages = [
        ("商品资料", "products", "Product", "product"),
        ("商品分类", "product-categories", "ProductCategory", "product_category"),
        ("计量单位", "units", "Unit", "unit"),
        ("单位换算", "unit-conversions", "UnitConversion", "unit_conversion"),
        ("客户资料", "customers", "Customer", "customer"),
        ("供应商资料", "suppliers", "Supplier", "supplier"),
        ("仓库资料", "warehouses", "Warehouse", "warehouse"),
        ("职员资料", "employees", "Employee", "employee"),
        ("结算方式", "settlement-methods", "SettlementMethod", "settlement_method"),
    ]
    for index, (title, path, component, permission) in enumerate(pages, 1):
        page_id = add(title, path, f"views/Erp/Master/{component}", root, order=index, perms=f"erp.master.{permission}.list")
        for action_index, (action_title, action) in enumerate((("查看", "view"), ("新增", "create"), ("修改", "update"), ("删除", "delete"))):
            add(action_title, parent_id=page_id, menu_type="2", order=action_index, perms=f"erp.master.{permission}.{action}")


def downgrade():
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM vadmin_auth_menu WHERE perms LIKE 'erp.master.%'"))
    bind.execute(sa.text("DELETE FROM vadmin_auth_menu WHERE path = '/erp'"))
    for table in (
        "erp_supplier", "erp_customer", "erp_unit_conversion", "erp_product", "erp_employee",
        "erp_warehouse", "erp_settlement_method", "erp_unit", "erp_product_category",
    ):
        op.drop_table(table)
