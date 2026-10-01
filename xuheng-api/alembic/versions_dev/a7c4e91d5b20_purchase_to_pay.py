"""Purchase-to-pay workflow.

Revision ID: a7c4e91d5b20
Revises: f41c8a73d2e9
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = "a7c4e91d5b20"
down_revision = "f41c8a73d2e9"
branch_labels = None
depends_on = None
OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


def base():
    """返回所有业务表的公共审计字段。"""

    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("create_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("update_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("delete_datetime", sa.DateTime()),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.false()),
    ]


def header(number):
    """返回采购订单、收货和退货共用表头字段。"""

    return base() + [
        sa.Column(number, sa.String(50), nullable=False), sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False), sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer()), sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("total_quantity", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("payable_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("remark", sa.Text()), sa.Column("created_by_id", sa.Integer()), sa.Column("approved_by_id", sa.Integer()),
        sa.Column("approved_at", sa.DateTime()), sa.Column("posting_version", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["supplier_id"], ["erp_supplier.id"]), sa.ForeignKeyConstraint(["warehouse_id"], ["erp_warehouse.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["erp_employee.id"]), sa.UniqueConstraint(number, name=f"uq_erp_{number}"),
    ]


def line():
    """返回采购商品明细共用字段。"""

    return base() + [
        sa.Column("line_no", sa.Integer(), nullable=False), sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False), sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("unit_to_base_rate", sa.DECIMAL(20, 8), nullable=False), sa.Column("quantity", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("base_quantity", sa.DECIMAL(20, 6), nullable=False), sa.Column("unit_price", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"), sa.Column("tax_rate", sa.DECIMAL(10, 4), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"), sa.Column("tax_inclusive_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("remark", sa.String(500)), sa.ForeignKeyConstraint(["product_id"], ["erp_product.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["erp_warehouse.id"]), sa.ForeignKeyConstraint(["unit_id"], ["erp_unit.id"]),
    ]


def upgrade():
    """创建采购订单到付款全链路表和菜单权限。"""

    op.create_table("erp_purchase_order", *header("order_no"), sa.Column("expected_receipt_date", sa.Date()), comment="采购订单", **OPTIONS)
    op.create_table("erp_purchase_order_line", *line(), sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("received_quantity", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["order_id"], ["erp_purchase_order.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("order_id", "line_no", name="uq_erp_purchase_order_line_no"), comment="采购订单明细", **OPTIONS)
    op.create_table("erp_purchase_receipt", *header("receipt_no"), sa.Column("order_id", sa.Integer()), sa.Column("due_date", sa.Date()),
        sa.ForeignKeyConstraint(["order_id"], ["erp_purchase_order.id"]), comment="采购收货单", **OPTIONS)
    op.create_table("erp_purchase_receipt_line", *line(), sa.Column("receipt_id", sa.Integer(), nullable=False), sa.Column("order_line_id", sa.Integer()),
        sa.Column("batch_no", sa.String(80)), sa.Column("production_date", sa.Date()), sa.Column("expiry_date", sa.Date()), sa.Column("serial_numbers", sa.Text()),
        sa.Column("returned_quantity", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["receipt_id"], ["erp_purchase_receipt.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["order_line_id"], ["erp_purchase_order_line.id"]),
        sa.UniqueConstraint("receipt_id", "line_no", name="uq_erp_purchase_receipt_line_no"), comment="采购收货明细", **OPTIONS)
    op.create_table("erp_purchase_return", *header("return_no"), sa.Column("receipt_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["receipt_id"], ["erp_purchase_receipt.id"]), comment="采购退货单", **OPTIONS)
    op.create_table("erp_purchase_return_line", *line(), sa.Column("return_id", sa.Integer(), nullable=False), sa.Column("receipt_line_id", sa.Integer(), nullable=False),
        sa.Column("batch_no", sa.String(80)), sa.Column("serial_numbers", sa.Text()),
        sa.ForeignKeyConstraint(["return_id"], ["erp_purchase_return.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["receipt_line_id"], ["erp_purchase_receipt_line.id"]),
        sa.UniqueConstraint("return_id", "line_no", name="uq_erp_purchase_return_line_no"), comment="采购退货明细", **OPTIONS)

    op.create_table("erp_supplier_payable_balance", *base(), sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"), sa.Column("last_entry_id", sa.Integer()), sa.Column("last_occurred_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["supplier_id"], ["erp_supplier.id"]), sa.UniqueConstraint("supplier_id", name="uq_erp_supplier_payable_balance"), comment="供应商应付余额", **OPTIONS)
    op.create_table("erp_payable", *base(), sa.Column("payable_no", sa.String(60), nullable=False), sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("receipt_id", sa.Integer(), nullable=False), sa.Column("receipt_no", sa.String(50), nullable=False), sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date()), sa.Column("original_amount", sa.DECIMAL(20, 4), nullable=False), sa.Column("settled_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("returned_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"), sa.Column("outstanding_amount", sa.DECIMAL(20, 4), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"), sa.ForeignKeyConstraint(["supplier_id"], ["erp_supplier.id"]),
        sa.ForeignKeyConstraint(["receipt_id"], ["erp_purchase_receipt.id"]), sa.UniqueConstraint("payable_no", name="uq_erp_payable_no"),
        sa.UniqueConstraint("receipt_id", name="uq_erp_payable_receipt"), comment="供应商应付项目", **OPTIONS)
    op.create_table("erp_payable_ledger", *base(), sa.Column("entry_no", sa.String(80), nullable=False), sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("entry_type", sa.String(30), nullable=False), sa.Column("supplier_id", sa.Integer(), nullable=False), sa.Column("payable_id", sa.Integer()),
        sa.Column("source_type", sa.String(30), nullable=False), sa.Column("source_id", sa.Integer(), nullable=False), sa.Column("source_no", sa.String(60), nullable=False),
        sa.Column("posting_version", sa.Integer(), nullable=False), sa.Column("reversal_of_id", sa.Integer()), sa.Column("amount", sa.DECIMAL(20, 4), nullable=False),
        sa.Column("balance_before", sa.DECIMAL(20, 4), nullable=False), sa.Column("balance_after", sa.DECIMAL(20, 4), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False), sa.Column("operator_id", sa.Integer()), sa.Column("remark", sa.String(500)),
        sa.ForeignKeyConstraint(["supplier_id"], ["erp_supplier.id"]), sa.ForeignKeyConstraint(["payable_id"], ["erp_payable.id"]),
        sa.ForeignKeyConstraint(["reversal_of_id"], ["erp_payable_ledger.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("entry_no", name="uq_erp_payable_ledger_no"), sa.UniqueConstraint("idempotency_key", name="uq_erp_payable_ledger_idempotency"), comment="不可变应付流水", **OPTIONS)
    op.create_table("erp_purchase_payment", *base(), sa.Column("payment_no", sa.String(50), nullable=False), sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False), sa.Column("settlement_method_id", sa.Integer()), sa.Column("amount", sa.DECIMAL(20, 4), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"), sa.Column("remark", sa.String(500)), sa.Column("created_by_id", sa.Integer()),
        sa.Column("approved_by_id", sa.Integer()), sa.Column("approved_at", sa.DateTime()), sa.Column("posting_version", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["supplier_id"], ["erp_supplier.id"]), sa.ForeignKeyConstraint(["settlement_method_id"], ["erp_settlement_method.id"]),
        sa.UniqueConstraint("payment_no", name="uq_erp_purchase_payment_no"), comment="采购付款单", **OPTIONS)
    op.create_table("erp_purchase_payment_allocation", *base(), sa.Column("payment_id", sa.Integer(), nullable=False), sa.Column("payable_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.DECIMAL(20, 4), nullable=False), sa.ForeignKeyConstraint(["payment_id"], ["erp_purchase_payment.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payable_id"], ["erp_payable.id"]), sa.UniqueConstraint("payment_id", "payable_id", name="uq_erp_purchase_payment_allocation"), comment="采购付款核销明细", **OPTIONS)
    install_menus()


def install_menus():
    """安装采购页面和按钮权限。"""

    bind = op.get_bind()
    root = bind.execute(sa.text("SELECT id FROM vadmin_auth_menu WHERE path='/erp' AND is_delete=0 LIMIT 1")).scalar()
    if not root:
        return
    menu = sa.table("vadmin_auth_menu", *[sa.column(x, sa.String if x in {"title", "icon", "redirect", "component", "path", "menu_type", "perms"} else sa.Integer if x in {"order", "parent_id"} else sa.Boolean) for x in ("title", "icon", "redirect", "component", "path", "disabled", "hidden", "order", "menu_type", "parent_id", "perms", "noCache", "breadcrumb", "affix", "noTagsView", "canTo", "alwaysShow", "is_delete")])
    def add(title, parent, kind, order, perms, path=None, component=None, icon=None):
        """插入一个页面或按钮菜单。"""

        return bind.execute(menu.insert().values(title=title, icon=icon, redirect=None, component=component, path=path, disabled=False, hidden=False, order=order, menu_type=kind, parent_id=parent, perms=perms, noCache=False, breadcrumb=True, affix=False, noTagsView=False, canTo=False, alwaysShow=False, is_delete=False)).lastrowid
    pages = (("采购订单", "order", "purchase-orders", "views/Erp/Purchase/Order", 30), ("采购收货", "receipt", "purchase-receipts", "views/Erp/Purchase/Receipt", 31), ("采购退货", "return", "purchase-returns", "views/Erp/Purchase/Return", 32), ("采购应付", "payable", "purchase-payables", "views/Erp/Purchase/Payable", 33))
    for title, code, path, component, order in pages:
        page = add(title, root, "1", order, f"erp.purchase.{code}.list", path, component, "ep:shopping-cart")
        for index, action in enumerate(("view", "create", "update", "delete", "approve", "unapprove")):
            add(action, page, "2", index, f"erp.purchase.{code}.{action}")


def downgrade():
    """移除采购菜单和全部 Purchase-to-Pay 表。"""

    op.get_bind().execute(sa.text("DELETE FROM vadmin_auth_menu WHERE perms LIKE 'erp.purchase.%'"))
    for table in ("erp_purchase_payment_allocation", "erp_purchase_payment", "erp_payable_ledger", "erp_payable", "erp_supplier_payable_balance", "erp_purchase_return_line", "erp_purchase_return", "erp_purchase_receipt_line", "erp_purchase_receipt", "erp_purchase_order_line", "erp_purchase_order"):
        op.drop_table(table)

