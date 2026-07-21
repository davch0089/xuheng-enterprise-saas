"""Complete sales order-to-cash flow.

Revision ID: b39e75dab642
Revises: a28d64c9b531
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa


revision = "b39e75dab642"
down_revision = "a28d64c9b531"
branch_labels = None
depends_on = None

OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


def base_columns():
    """Return columns shared by all application tables."""

    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("create_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("update_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("delete_datetime", sa.DateTime(), nullable=True),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.false()),
    ]


def document_columns():
    """Return common sales document header columns."""

    return [
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column("delivery_address", sa.String(255), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("total_quantity", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("payable_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("posting_version", sa.Integer(), nullable=False, server_default="0"),
    ]


def line_columns():
    """Return common sales document line columns."""

    return [
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("unit_to_base_rate", sa.DECIMAL(20, 8), nullable=False),
        sa.Column("quantity", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("base_quantity", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("unit_price", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("discount_rate", sa.DECIMAL(10, 4), nullable=False, server_default="100"),
        sa.Column("amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.DECIMAL(10, 4), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("tax_inclusive_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("remark", sa.String(500), nullable=True),
    ]


def master_foreign_keys():
    """Return common sales document master-data foreign keys."""

    return [
        sa.ForeignKeyConstraint(["customer_id"], ["erp_customer.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["erp_warehouse.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["erp_employee.id"]),
    ]


def line_foreign_keys():
    """Return common sales line master-data foreign keys."""

    return [
        sa.ForeignKeyConstraint(["product_id"], ["erp_product.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["erp_warehouse.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["erp_unit.id"]),
    ]


def upgrade():
    """Create sales order-to-cash tables and permissions."""

    op.create_table(
        "erp_sales_order",
        sa.Column("order_no", sa.String(50), nullable=False),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        *document_columns(), *base_columns(), *master_foreign_keys(),
        sa.UniqueConstraint("order_no", name="uq_erp_sales_order_no"),
        comment="销售订单", **OPTIONS,
    )
    _header_indexes("erp_sales_order", "order_no")
    op.create_table(
        "erp_sales_order_line",
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("delivered_quantity", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        *line_columns(), *base_columns(), *line_foreign_keys(),
        sa.ForeignKeyConstraint(["order_id"], ["erp_sales_order.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("order_id", "line_no", name="uq_erp_sales_order_line_no"),
        comment="销售订单明细", **OPTIONS,
    )
    op.create_index("ix_erp_sales_order_line_order_id", "erp_sales_order_line", ["order_id"])
    op.create_index("ix_erp_sales_order_line_product_id", "erp_sales_order_line", ["product_id"])

    op.create_table(
        "erp_sales_delivery",
        sa.Column("delivery_no", sa.String(50), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("total_cost", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("gross_profit", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        *document_columns(), *base_columns(), *master_foreign_keys(),
        sa.ForeignKeyConstraint(["order_id"], ["erp_sales_order.id"]),
        sa.UniqueConstraint("delivery_no", name="uq_erp_sales_delivery_no"),
        comment="销售出库单", **OPTIONS,
    )
    _header_indexes("erp_sales_delivery", "delivery_no")
    op.create_index("ix_erp_sales_delivery_order_id", "erp_sales_delivery", ["order_id"])
    op.create_table(
        "erp_sales_delivery_line",
        sa.Column("delivery_id", sa.Integer(), nullable=False),
        sa.Column("order_line_id", sa.Integer(), nullable=True),
        sa.Column("batch_no", sa.String(80), nullable=True),
        sa.Column("serial_numbers", sa.Text(), nullable=True),
        sa.Column("unit_cost", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("cost_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("returned_quantity", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        *line_columns(), *base_columns(), *line_foreign_keys(),
        sa.ForeignKeyConstraint(["delivery_id"], ["erp_sales_delivery.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_line_id"], ["erp_sales_order_line.id"]),
        sa.UniqueConstraint("delivery_id", "line_no", name="uq_erp_sales_delivery_line_no"),
        comment="销售出库单明细", **OPTIONS,
    )
    op.create_index("ix_erp_sales_delivery_line_delivery_id", "erp_sales_delivery_line", ["delivery_id"])
    op.create_index("ix_erp_sales_delivery_line_order_line_id", "erp_sales_delivery_line", ["order_line_id"])
    op.create_index("ix_erp_sales_delivery_line_product_id", "erp_sales_delivery_line", ["product_id"])

    op.create_table(
        "erp_sales_return",
        sa.Column("return_no", sa.String(50), nullable=False),
        sa.Column("delivery_id", sa.Integer(), nullable=False),
        sa.Column("total_cost", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        *document_columns(), *base_columns(), *master_foreign_keys(),
        sa.ForeignKeyConstraint(["delivery_id"], ["erp_sales_delivery.id"]),
        sa.UniqueConstraint("return_no", name="uq_erp_sales_return_no"),
        comment="销售退货单", **OPTIONS,
    )
    _header_indexes("erp_sales_return", "return_no")
    op.create_index("ix_erp_sales_return_delivery_id", "erp_sales_return", ["delivery_id"])
    op.create_table(
        "erp_sales_return_line",
        sa.Column("return_id", sa.Integer(), nullable=False),
        sa.Column("delivery_line_id", sa.Integer(), nullable=False),
        sa.Column("batch_no", sa.String(80), nullable=True),
        sa.Column("serial_numbers", sa.Text(), nullable=True),
        sa.Column("unit_cost", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("cost_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        *line_columns(), *base_columns(), *line_foreign_keys(),
        sa.ForeignKeyConstraint(["return_id"], ["erp_sales_return.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delivery_line_id"], ["erp_sales_delivery_line.id"]),
        sa.UniqueConstraint("return_id", "line_no", name="uq_erp_sales_return_line_no"),
        comment="销售退货单明细", **OPTIONS,
    )
    op.create_index("ix_erp_sales_return_line_return_id", "erp_sales_return_line", ["return_id"])
    op.create_index("ix_erp_sales_return_line_delivery_line_id", "erp_sales_return_line", ["delivery_line_id"])

    op.create_table(
        "erp_stock_reservation",
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("source_line_id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("released_quantity", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        *base_columns(),
        sa.ForeignKeyConstraint(["warehouse_id"], ["erp_warehouse.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["erp_product.id"]),
        sa.UniqueConstraint("source_type", "source_line_id", name="uq_erp_stock_reservation_source"),
        comment="库存预留", **OPTIONS,
    )
    for column in ("source_type", "source_id", "source_line_id", "warehouse_id", "product_id", "status"):
        op.create_index(f"ix_erp_stock_reservation_{column}", "erp_stock_reservation", [column])

    op.create_table(
        "erp_customer_receivable_balance",
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("last_entry_id", sa.Integer(), nullable=True),
        sa.Column("last_occurred_at", sa.DateTime(), nullable=True),
        *base_columns(),
        sa.ForeignKeyConstraint(["customer_id"], ["erp_customer.id"]),
        sa.UniqueConstraint("customer_id", name="uq_erp_customer_receivable_balance"),
        comment="客户应收余额", **OPTIONS,
    )
    op.create_index("ix_erp_customer_receivable_balance_customer_id", "erp_customer_receivable_balance", ["customer_id"])
    op.create_table(
        "erp_receivable",
        sa.Column("receivable_no", sa.String(60), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("delivery_id", sa.Integer(), nullable=False),
        sa.Column("delivery_no", sa.String(50), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("original_amount", sa.DECIMAL(20, 4), nullable=False),
        sa.Column("settled_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("returned_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("outstanding_amount", sa.DECIMAL(20, 4), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        *base_columns(),
        sa.ForeignKeyConstraint(["customer_id"], ["erp_customer.id"]),
        sa.ForeignKeyConstraint(["delivery_id"], ["erp_sales_delivery.id"]),
        sa.UniqueConstraint("receivable_no", name="uq_erp_receivable_no"),
        sa.UniqueConstraint("delivery_id", name="uq_erp_receivable_delivery"),
        comment="客户应收项目", **OPTIONS,
    )
    for column in ("receivable_no", "customer_id", "delivery_no", "business_date", "due_date", "status"):
        op.create_index(f"ix_erp_receivable_{column}", "erp_receivable", [column])
    op.create_table(
        "erp_receivable_ledger",
        sa.Column("entry_no", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("entry_type", sa.String(30), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("receivable_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("source_no", sa.String(60), nullable=False),
        sa.Column("posting_version", sa.Integer(), nullable=False),
        sa.Column("reversal_of_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.DECIMAL(20, 4), nullable=False),
        sa.Column("balance_before", sa.DECIMAL(20, 4), nullable=False),
        sa.Column("balance_after", sa.DECIMAL(20, 4), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("operator_id", sa.Integer(), nullable=True),
        sa.Column("remark", sa.String(500), nullable=True),
        *base_columns(),
        sa.ForeignKeyConstraint(["customer_id"], ["erp_customer.id"]),
        sa.ForeignKeyConstraint(["receivable_id"], ["erp_receivable.id"]),
        sa.ForeignKeyConstraint(["reversal_of_id"], ["erp_receivable_ledger.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("entry_no", name="uq_erp_receivable_ledger_no"),
        sa.UniqueConstraint("idempotency_key", name="uq_erp_receivable_ledger_idempotency"),
        comment="不可变应收流水", **OPTIONS,
    )
    for column in ("entry_no", "idempotency_key", "entry_type", "customer_id", "receivable_id", "source_type", "source_id", "source_no", "reversal_of_id", "occurred_at"):
        op.create_index(f"ix_erp_receivable_ledger_{column}", "erp_receivable_ledger", [column])

    op.create_table(
        "erp_sales_receipt",
        sa.Column("receipt_no", sa.String(50), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("settlement_method_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.DECIMAL(20, 4), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("remark", sa.String(500), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("posting_version", sa.Integer(), nullable=False, server_default="0"),
        *base_columns(),
        sa.ForeignKeyConstraint(["customer_id"], ["erp_customer.id"]),
        sa.ForeignKeyConstraint(["settlement_method_id"], ["erp_settlement_method.id"]),
        sa.UniqueConstraint("receipt_no", name="uq_erp_sales_receipt_no"),
        comment="销售收款单", **OPTIONS,
    )
    for column in ("receipt_no", "receipt_date", "customer_id", "status"):
        op.create_index(f"ix_erp_sales_receipt_{column}", "erp_sales_receipt", [column])
    op.create_table(
        "erp_sales_receipt_allocation",
        sa.Column("receipt_id", sa.Integer(), nullable=False),
        sa.Column("receivable_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.DECIMAL(20, 4), nullable=False),
        *base_columns(),
        sa.ForeignKeyConstraint(["receipt_id"], ["erp_sales_receipt.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["receivable_id"], ["erp_receivable.id"]),
        sa.UniqueConstraint("receipt_id", "receivable_id", name="uq_erp_sales_receipt_allocation"),
        comment="销售收款核销明细", **OPTIONS,
    )
    op.create_index("ix_erp_sales_receipt_allocation_receipt_id", "erp_sales_receipt_allocation", ["receipt_id"])
    op.create_index("ix_erp_sales_receipt_allocation_receivable_id", "erp_sales_receipt_allocation", ["receivable_id"])
    _insert_menus()


def _header_indexes(table, number_column):
    """Create common indexes for a sales document header."""

    for column in (number_column, "business_date", "customer_id", "status"):
        op.create_index(f"ix_{table}_{column}", table, [column])


def _insert_menus():
    """Insert sales pages and action permissions into HengFlow ERP menus."""

    bind = op.get_bind()
    root_id = bind.execute(
        sa.text("SELECT id FROM vadmin_auth_menu WHERE path='/erp' AND is_delete=0 LIMIT 1")
    ).scalar()
    if not root_id:
        return
    menu = sa.table(
        "vadmin_auth_menu",
        sa.column("title", sa.String), sa.column("icon", sa.String),
        sa.column("redirect", sa.String), sa.column("component", sa.String),
        sa.column("path", sa.String), sa.column("disabled", sa.Boolean),
        sa.column("hidden", sa.Boolean), sa.column("order", sa.Integer),
        sa.column("menu_type", sa.String), sa.column("parent_id", sa.Integer),
        sa.column("perms", sa.String), sa.column("noCache", sa.Boolean),
        sa.column("breadcrumb", sa.Boolean), sa.column("affix", sa.Boolean),
        sa.column("noTagsView", sa.Boolean), sa.column("canTo", sa.Boolean),
        sa.column("alwaysShow", sa.Boolean), sa.column("is_delete", sa.Boolean),
    )

    def add(title, parent_id, menu_type, order, perms, path=None, component=None, icon=None):
        """Insert one menu or permission row and return its ID."""

        result = bind.execute(menu.insert().values(
            title=title, icon=icon, redirect=None, component=component, path=path,
            disabled=False, hidden=False, order=order, menu_type=menu_type,
            parent_id=parent_id, perms=perms, noCache=False, breadcrumb=True,
            affix=False, noTagsView=False, canTo=False, alwaysShow=False, is_delete=False,
        ))
        return result.lastrowid

    pages = (
        ("销售订单", "order", "sales-orders", "views/Erp/Sales/Order", "ep:document", 30),
        ("销售出库", "delivery", "sales-deliveries", "views/Erp/Sales/Delivery", "ep:upload", 31),
        ("销售退货", "return", "sales-returns", "views/Erp/Sales/Return", "ep:back", 32),
        ("应收收款", "receipt", "sales-receivables", "views/Erp/Sales/Receivable", "ep:money", 33),
    )
    for title, code, path, component, icon, order in pages:
        page_id = add(title, root_id, "1", order, f"erp.sales.{code}.list", path, component, icon)
        for action_order, (action_title, action) in enumerate((
            ("查看", "view"), ("新增", "create"), ("修改", "update"),
            ("删除", "delete"), ("审核", "approve"), ("反审核", "unapprove"),
        )):
            add(action_title, page_id, "2", action_order, f"erp.sales.{code}.{action}")
    receivable_page = bind.execute(
        sa.text("SELECT id FROM vadmin_auth_menu WHERE perms='erp.sales.receipt.list' LIMIT 1")
    ).scalar()
    add("查看应收", receivable_page, "2", 10, "erp.sales.receivable.list")


def downgrade():
    """Remove sales menus and all order-to-cash tables."""

    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM vadmin_auth_menu WHERE perms LIKE 'erp.sales.%'"))
    for table in (
        "erp_sales_receipt_allocation",
        "erp_sales_receipt",
        "erp_receivable_ledger",
        "erp_receivable",
        "erp_customer_receivable_balance",
        "erp_stock_reservation",
        "erp_sales_return_line",
        "erp_sales_return",
        "erp_sales_delivery_line",
        "erp_sales_delivery",
        "erp_sales_order_line",
        "erp_sales_order",
    ):
        op.drop_table(table)
