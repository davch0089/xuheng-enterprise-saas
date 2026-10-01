"""Complete inventory operations flow.

Revision ID: c7e4a19f2d81
Revises: b39e75dab642
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = "c7e4a19f2d81"
down_revision = "b39e75dab642"
branch_labels = None
depends_on = None
OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


def base_columns():
    """Return columns shared by application tables."""

    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("create_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("update_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("delete_datetime", sa.DateTime()),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.false()),
    ]


def tracked_columns():
    """Return common tracked-stock detail columns."""

    return [
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("unit_to_base_rate", sa.DECIMAL(20, 8), nullable=False),
        sa.Column("quantity", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("base_quantity", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("batch_no", sa.String(80)),
        sa.Column("production_date", sa.Date()),
        sa.Column("expiry_date", sa.Date()),
        sa.Column("serial_numbers", sa.Text()),
        sa.Column("remark", sa.String(500)),
        sa.ForeignKeyConstraint(["product_id"], ["erp_product.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["erp_unit.id"]),
    ]


def upgrade():
    """Create inventory operation tables, serial batch dimension and menus."""

    op.add_column("erp_inventory_serial", sa.Column("batch_no", sa.String(80), nullable=True))
    op.create_index("ix_erp_inventory_serial_batch_no", "erp_inventory_serial", ["batch_no"])
    op.execute(
        "UPDATE erp_inventory_serial s LEFT JOIN erp_inventory_ledger l "
        "ON l.id=s.last_movement_id SET s.batch_no=l.batch_no"
    )

    op.create_table(
        "erp_stock_transfer",
        *base_columns(),
        sa.Column("transfer_no", sa.String(50), nullable=False),
        sa.Column("transfer_date", sa.Date(), nullable=False),
        sa.Column("transfer_mode", sa.String(20), nullable=False, server_default="one_step"),
        sa.Column("source_warehouse_id", sa.Integer(), nullable=False),
        sa.Column("destination_warehouse_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer()),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("total_quantity", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("remark", sa.Text()),
        sa.Column("created_by_id", sa.Integer()),
        sa.Column("dispatched_by_id", sa.Integer()),
        sa.Column("dispatched_at", sa.DateTime()),
        sa.Column("received_by_id", sa.Integer()),
        sa.Column("received_at", sa.DateTime()),
        sa.Column("posting_version", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["source_warehouse_id"], ["erp_warehouse.id"]),
        sa.ForeignKeyConstraint(["destination_warehouse_id"], ["erp_warehouse.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["erp_employee.id"]),
        sa.UniqueConstraint("transfer_no", name="uq_erp_stock_transfer_no"),
        comment="库存调拨单", **OPTIONS,
    )
    op.create_index("ix_erp_stock_transfer_status", "erp_stock_transfer", ["status"])
    op.create_index("ix_erp_stock_transfer_date", "erp_stock_transfer", ["transfer_date"])
    op.create_table(
        "erp_stock_transfer_line",
        *base_columns(), *tracked_columns(),
        sa.Column("transfer_id", sa.Integer(), nullable=False),
        sa.Column("transfer_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["transfer_id"], ["erp_stock_transfer.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("transfer_id", "line_no", name="uq_erp_stock_transfer_line_no"),
        comment="库存调拨明细", **OPTIONS,
    )
    op.create_index("ix_erp_stock_transfer_line_transfer", "erp_stock_transfer_line", ["transfer_id"])

    op.create_table(
        "erp_inventory_count",
        *base_columns(),
        sa.Column("count_no", sa.String(50), nullable=False),
        sa.Column("count_date", sa.Date(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer()),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("total_lines", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_system_quantity", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("total_counted_quantity", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("total_gain_quantity", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("total_loss_quantity", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("remark", sa.Text()),
        sa.Column("created_by_id", sa.Integer()),
        sa.Column("approved_by_id", sa.Integer()),
        sa.Column("approved_at", sa.DateTime()),
        sa.Column("posting_version", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["erp_warehouse.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["erp_employee.id"]),
        sa.UniqueConstraint("count_no", name="uq_erp_inventory_count_no"),
        comment="库存盘点单", **OPTIONS,
    )
    op.create_index("ix_erp_inventory_count_status", "erp_inventory_count", ["status"])
    op.create_table(
        "erp_inventory_count_line",
        *base_columns(),
        sa.Column("count_id", sa.Integer(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("system_quantity", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("counted_quantity", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("difference_quantity", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("snapshot_unit_cost", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("batch_no", sa.String(80)),
        sa.Column("production_date", sa.Date()),
        sa.Column("expiry_date", sa.Date()),
        sa.Column("system_serial_numbers", sa.Text()),
        sa.Column("counted_serial_numbers", sa.Text()),
        sa.Column("remark", sa.String(500)),
        sa.ForeignKeyConstraint(["count_id"], ["erp_inventory_count.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["erp_product.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["erp_unit.id"]),
        sa.UniqueConstraint("count_id", "line_no", name="uq_erp_inventory_count_line_no"),
        comment="库存盘点明细", **OPTIONS,
    )
    op.create_index("ix_erp_inventory_count_line_count", "erp_inventory_count_line", ["count_id"])

    op.create_table(
        "erp_other_stock_order",
        *base_columns(),
        sa.Column("order_no", sa.String(50), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer()),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("total_quantity", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("remark", sa.Text()),
        sa.Column("created_by_id", sa.Integer()),
        sa.Column("approved_by_id", sa.Integer()),
        sa.Column("approved_at", sa.DateTime()),
        sa.Column("posting_version", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["erp_warehouse.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["erp_employee.id"]),
        sa.UniqueConstraint("order_no", name="uq_erp_other_stock_order_no"),
        comment="其他出入库单", **OPTIONS,
    )
    op.create_index("ix_erp_other_stock_order_status", "erp_other_stock_order", ["status"])
    op.create_table(
        "erp_other_stock_order_line",
        *base_columns(), *tracked_columns(),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["order_id"], ["erp_other_stock_order.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("order_id", "line_no", name="uq_erp_other_stock_order_line_no"),
        comment="其他出入库明细", **OPTIONS,
    )
    op.create_index("ix_erp_other_stock_order_line_order", "erp_other_stock_order_line", ["order_id"])
    install_menus()


def install_menus():
    """Install inventory-operation pages and button permissions."""

    bind = op.get_bind()
    root_id = bind.execute(sa.text("SELECT id FROM vadmin_auth_menu WHERE path='/erp' AND is_delete=0 LIMIT 1")).scalar()
    if not root_id:
        return
    menu = sa.table(
        "vadmin_auth_menu", sa.column("title", sa.String), sa.column("icon", sa.String),
        sa.column("redirect", sa.String), sa.column("component", sa.String), sa.column("path", sa.String),
        sa.column("disabled", sa.Boolean), sa.column("hidden", sa.Boolean), sa.column("order", sa.Integer),
        sa.column("menu_type", sa.String), sa.column("parent_id", sa.Integer), sa.column("perms", sa.String),
        sa.column("noCache", sa.Boolean), sa.column("breadcrumb", sa.Boolean), sa.column("affix", sa.Boolean),
        sa.column("noTagsView", sa.Boolean), sa.column("canTo", sa.Boolean), sa.column("alwaysShow", sa.Boolean),
        sa.column("is_delete", sa.Boolean),
    )

    def add(title, parent, menu_type, order, perms, path=None, component=None, icon=None):
        """Insert one menu or permission row."""

        return bind.execute(menu.insert().values(
            title=title, icon=icon, redirect=None, component=component, path=path,
            disabled=False, hidden=False, order=order, menu_type=menu_type, parent_id=parent,
            perms=perms, noCache=False, breadcrumb=True, affix=False, noTagsView=False,
            canTo=False, alwaysShow=False, is_delete=False,
        )).lastrowid

    pages = (
        ("库存调拨", "transfer", "stock-transfers", "views/Erp/Inventory/Transfer", "ep:switch", 21, ("view", "create", "update", "delete", "dispatch", "receive", "unreceive", "undispatch")),
        ("库存盘点", "count", "inventory-counts", "views/Erp/Inventory/Count", "ep:checked", 22, ("view", "create", "update", "delete", "approve", "unapprove")),
        ("其他出入库", "other", "other-stock", "views/Erp/Inventory/Other", "ep:sort", 23, ("view", "create", "update", "delete", "approve", "unapprove")),
    )
    for title, code, path, component, icon, order, actions in pages:
        page_id = add(title, root_id, "1", order, f"erp.inventory.{code}.list", path, component, icon)
        for action_order, action in enumerate(actions):
            add(action, page_id, "2", action_order, f"erp.inventory.{code}.{action}")


def downgrade():
    """Remove inventory operation menus, tables and serial batch dimension."""

    op.get_bind().execute(sa.text("DELETE FROM vadmin_auth_menu WHERE perms LIKE 'erp.inventory.transfer.%' OR perms LIKE 'erp.inventory.count.%' OR perms LIKE 'erp.inventory.other.%'"))
    for table in ("erp_other_stock_order_line", "erp_other_stock_order", "erp_inventory_count_line", "erp_inventory_count", "erp_stock_transfer_line", "erp_stock_transfer"):
        op.drop_table(table)
    op.drop_index("ix_erp_inventory_serial_batch_no", table_name="erp_inventory_serial")
    op.drop_column("erp_inventory_serial", "batch_no")
