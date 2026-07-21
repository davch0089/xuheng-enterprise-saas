"""ERP inbound receipt and inventory ledger.

Revision ID: d95a31f6e208
Revises: c84e19a2d740
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa


revision = "d95a31f6e208"
down_revision = "c84e19a2d740"
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


OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


def upgrade():
    op.create_table(
        "erp_document_sequence",
        sa.Column("document_type", sa.String(30), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("current_value", sa.Integer(), nullable=False, server_default="0"),
        *base_columns(),
        sa.UniqueConstraint("document_type", "business_date", name="uq_erp_document_sequence"),
        comment="ERP单据编号序列", **OPTIONS,
    )
    op.create_table(
        "erp_inbound_receipt",
        sa.Column("receipt_no", sa.String(40), nullable=False, comment="入库单号"),
        sa.Column("receipt_date", sa.Date(), nullable=False, comment="业务日期"),
        sa.Column("business_type", sa.String(30), nullable=False, server_default="other", comment="业务类型"),
        sa.Column("supplier_id", sa.Integer(), nullable=True, comment="供应商"),
        sa.Column("warehouse_id", sa.Integer(), nullable=False, comment="默认仓库"),
        sa.Column("employee_id", sa.Integer(), nullable=True, comment="经办人"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft", comment="状态"),
        sa.Column("total_quantity", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("posting_version", sa.Integer(), nullable=False, server_default="0"),
        *base_columns(),
        sa.ForeignKeyConstraint(["supplier_id"], ["erp_supplier.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["erp_warehouse.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["erp_employee.id"]),
        sa.UniqueConstraint("receipt_no", name="uq_erp_inbound_receipt_no"),
        comment="入库单", **OPTIONS,
    )
    op.create_index("ix_erp_inbound_receipt_receipt_no", "erp_inbound_receipt", ["receipt_no"])
    op.create_index("ix_erp_inbound_receipt_receipt_date", "erp_inbound_receipt", ["receipt_date"])
    op.create_index("ix_erp_inbound_receipt_status", "erp_inbound_receipt", ["status"])
    op.create_table(
        "erp_inbound_receipt_line",
        sa.Column("receipt_id", sa.Integer(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("unit_to_base_rate", sa.DECIMAL(20, 8), nullable=False),
        sa.Column("quantity", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("base_quantity", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("unit_price", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("base_unit_cost", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("batch_no", sa.String(80), nullable=True),
        sa.Column("production_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("serial_numbers", sa.Text(), nullable=True),
        sa.Column("remark", sa.String(500), nullable=True),
        *base_columns(),
        sa.ForeignKeyConstraint(["receipt_id"], ["erp_inbound_receipt.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["erp_product.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["erp_warehouse.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["erp_unit.id"]),
        sa.UniqueConstraint("receipt_id", "line_no", name="uq_erp_inbound_receipt_line_no"),
        comment="入库单明细", **OPTIONS,
    )
    op.create_index("ix_erp_inbound_receipt_line_receipt_id", "erp_inbound_receipt_line", ["receipt_id"])
    op.create_index("ix_erp_inbound_receipt_line_product_id", "erp_inbound_receipt_line", ["product_id"])
    op.create_table(
        "erp_inventory_balance",
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("available_quantity", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("average_cost", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("inventory_value", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("last_movement_at", sa.DateTime(), nullable=True),
        *base_columns(),
        sa.ForeignKeyConstraint(["warehouse_id"], ["erp_warehouse.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["erp_product.id"]),
        sa.UniqueConstraint("warehouse_id", "product_id", name="uq_erp_inventory_balance"),
        comment="库存余额", **OPTIONS,
    )
    op.create_index("ix_erp_inventory_balance_warehouse_id", "erp_inventory_balance", ["warehouse_id"])
    op.create_index("ix_erp_inventory_balance_product_id", "erp_inventory_balance", ["product_id"])
    op.create_table(
        "erp_inventory_ledger",
        sa.Column("movement_no", sa.String(60), nullable=False),
        sa.Column("business_type", sa.String(30), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("business_line_id", sa.Integer(), nullable=False),
        sa.Column("posting_version", sa.Integer(), nullable=False),
        sa.Column("direction", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("amount", sa.DECIMAL(20, 4), nullable=False),
        sa.Column("balance_quantity_before", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("balance_quantity_after", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("average_cost_before", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("average_cost_after", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("operator_id", sa.Integer(), nullable=True),
        *base_columns(),
        sa.ForeignKeyConstraint(["warehouse_id"], ["erp_warehouse.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["erp_product.id"]),
        sa.UniqueConstraint("movement_no", name="uq_erp_inventory_ledger_movement_no"),
        comment="库存收发流水", **OPTIONS,
    )
    for name in ("movement_no", "business_type", "business_id", "business_line_id", "warehouse_id", "product_id", "occurred_at"):
        op.create_index(f"ix_erp_inventory_ledger_{name}", "erp_inventory_ledger", [name])
    op.create_table(
        "erp_inventory_batch_balance",
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("batch_no", sa.String(80), nullable=False),
        sa.Column("production_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("quantity", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        *base_columns(),
        sa.ForeignKeyConstraint(["warehouse_id"], ["erp_warehouse.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["erp_product.id"]),
        sa.UniqueConstraint("warehouse_id", "product_id", "batch_no", name="uq_erp_inventory_batch_balance"),
        comment="批次库存余额", **OPTIONS,
    )
    op.create_table(
        "erp_inventory_serial",
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("serial_no", sa.String(120), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_stock"),
        sa.Column("inbound_receipt_id", sa.Integer(), nullable=False),
        sa.Column("inbound_line_id", sa.Integer(), nullable=False),
        sa.Column("inbound_at", sa.DateTime(), nullable=False),
        *base_columns(),
        sa.ForeignKeyConstraint(["product_id"], ["erp_product.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["erp_warehouse.id"]),
        sa.ForeignKeyConstraint(["inbound_receipt_id"], ["erp_inbound_receipt.id"]),
        sa.ForeignKeyConstraint(["inbound_line_id"], ["erp_inbound_receipt_line.id"]),
        sa.UniqueConstraint("product_id", "serial_no", name="uq_erp_inventory_serial"),
        comment="序列号库存", **OPTIONS,
    )
    op.create_index("ix_erp_inventory_serial_product_id", "erp_inventory_serial", ["product_id"])
    op.create_index("ix_erp_inventory_serial_serial_no", "erp_inventory_serial", ["serial_no"])
    _insert_menus()


def _insert_menus():
    bind = op.get_bind()
    root_id = bind.execute(sa.text("SELECT id FROM vadmin_auth_menu WHERE path='/erp' AND is_delete=0 LIMIT 1")).scalar()
    if not root_id:
        return
    menu = sa.table(
        "vadmin_auth_menu",
        sa.column("title", sa.String), sa.column("icon", sa.String), sa.column("redirect", sa.String),
        sa.column("component", sa.String), sa.column("path", sa.String), sa.column("disabled", sa.Boolean),
        sa.column("hidden", sa.Boolean), sa.column("order", sa.Integer), sa.column("menu_type", sa.String),
        sa.column("parent_id", sa.Integer), sa.column("perms", sa.String), sa.column("noCache", sa.Boolean),
        sa.column("breadcrumb", sa.Boolean), sa.column("affix", sa.Boolean), sa.column("noTagsView", sa.Boolean),
        sa.column("canTo", sa.Boolean), sa.column("alwaysShow", sa.Boolean), sa.column("is_delete", sa.Boolean),
    )

    def add(title, parent_id, menu_type, order, perms, path=None, component=None, icon=None):
        result = bind.execute(menu.insert().values(
            title=title, icon=icon, redirect=None, component=component, path=path,
            disabled=False, hidden=False, order=order, menu_type=menu_type, parent_id=parent_id,
            perms=perms, noCache=False, breadcrumb=True, affix=False, noTagsView=False,
            canTo=False, alwaysShow=False, is_delete=False,
        ))
        return result.lastrowid

    page_id = add(
        "入库管理", root_id, "1", 20, "erp.inventory.inbound.list",
        path="inbounds", component="views/Erp/Inventory/Inbound", icon="ep:download",
    )
    for order, (title, action) in enumerate((
        ("查看", "view"), ("新增", "create"), ("修改", "update"), ("删除", "delete"),
        ("审核", "approve"), ("反审核", "unapprove"),
    )):
        add(title, page_id, "2", order, f"erp.inventory.inbound.{action}")


def downgrade():
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM vadmin_auth_menu WHERE perms LIKE 'erp.inventory.inbound.%'"))
    for table in (
        "erp_inventory_serial", "erp_inventory_batch_balance", "erp_inventory_ledger",
        "erp_inventory_balance", "erp_inbound_receipt_line", "erp_inbound_receipt", "erp_document_sequence",
    ):
        op.drop_table(table)
