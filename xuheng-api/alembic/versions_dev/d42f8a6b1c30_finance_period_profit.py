"""Add funds, settlements, accounting periods and profit reporting.

Revision ID: d42f8a6b1c30
Revises: c91d7e4a2b60
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa


revision = "d42f8a6b1c30"
down_revision = "c91d7e4a2b60"
branch_labels = None
depends_on = None
OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


def base():
    """返回 序衡 业务表审计字段。"""

    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("create_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("update_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("delete_datetime", sa.DateTime()),
        sa.Column("is_delete", sa.Boolean(), server_default=sa.false(), nullable=False),
    ]


def upgrade():
    """创建财务表、连接原收付款单并安装菜单权限。"""

    op.create_table("erp_accounting_period", *base(),
        sa.Column("period_code", sa.String(20), nullable=False), sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("closed_by_id", sa.Integer()), sa.Column("closed_at", sa.DateTime()),
        sa.Column("closing_version", sa.Integer(), nullable=False, server_default="0"), sa.Column("remark", sa.String(500)),
        sa.UniqueConstraint("period_code", name="uq_erp_accounting_period_code"), comment="会计期间", **OPTIONS)
    op.create_index("ix_erp_accounting_period_code", "erp_accounting_period", ["period_code"])
    op.create_index("ix_erp_accounting_period_start_date", "erp_accounting_period", ["start_date"])
    op.create_index("ix_erp_accounting_period_end_date", "erp_accounting_period", ["end_date"])
    op.create_index("ix_erp_accounting_period_status", "erp_accounting_period", ["status"])

    op.create_table("erp_fund_account", *base(),
        sa.Column("code", sa.String(50), nullable=False), sa.Column("name", sa.String(100), nullable=False),
        sa.Column("account_type", sa.String(30), nullable=False, server_default="bank"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="CNY"), sa.Column("bank_name", sa.String(100)),
        sa.Column("account_no", sa.String(80)), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.String(500)), sa.UniqueConstraint("code", name="uq_erp_fund_account_code"), comment="资金账户", **OPTIONS)
    op.create_index("ix_erp_fund_account_code", "erp_fund_account", ["code"])
    op.create_index("ix_erp_fund_account_name", "erp_fund_account", ["name"])
    op.create_table("erp_fund_account_balance", *base(), sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"), sa.Column("last_entry_id", sa.Integer()),
        sa.Column("last_occurred_at", sa.DateTime()), sa.ForeignKeyConstraint(["account_id"], ["erp_fund_account.id"]),
        sa.UniqueConstraint("account_id", name="uq_erp_fund_account_balance"), comment="资金账户余额", **OPTIONS)
    op.create_index("ix_erp_fund_account_balance_account_id", "erp_fund_account_balance", ["account_id"])
    op.create_table("erp_fund_document", *base(), sa.Column("document_no", sa.String(50), nullable=False),
        sa.Column("document_type", sa.String(20), nullable=False), sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("from_account_id", sa.Integer()), sa.Column("to_account_id", sa.Integer()),
        sa.Column("amount", sa.DECIMAL(20, 4), nullable=False), sa.Column("counterparty", sa.String(150)),
        sa.Column("profit_category", sa.String(30), nullable=False, server_default="none"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("posting_version", sa.Integer(), nullable=False, server_default="0"), sa.Column("created_by_id", sa.Integer()),
        sa.Column("approved_by_id", sa.Integer()), sa.Column("approved_at", sa.DateTime()), sa.Column("remark", sa.Text()),
        sa.ForeignKeyConstraint(["from_account_id"], ["erp_fund_account.id"]), sa.ForeignKeyConstraint(["to_account_id"], ["erp_fund_account.id"]),
        sa.UniqueConstraint("document_no", name="uq_erp_fund_document_no"), comment="资金单据", **OPTIONS)
    for column in ("document_no", "document_type", "business_date", "status"):
        op.create_index(f"ix_erp_fund_document_{column}", "erp_fund_document", [column])
    op.create_table("erp_fund_ledger", *base(), sa.Column("entry_no", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False), sa.Column("entry_type", sa.String(30), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False), sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False), sa.Column("source_no", sa.String(60), nullable=False),
        sa.Column("posting_version", sa.Integer(), nullable=False), sa.Column("reversal_of_id", sa.Integer()),
        sa.Column("amount", sa.DECIMAL(20, 4), nullable=False), sa.Column("balance_before", sa.DECIMAL(20, 4), nullable=False),
        sa.Column("balance_after", sa.DECIMAL(20, 4), nullable=False), sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("operator_id", sa.Integer()), sa.Column("remark", sa.String(500)),
        sa.ForeignKeyConstraint(["account_id"], ["erp_fund_account.id"]),
        sa.ForeignKeyConstraint(["reversal_of_id"], ["erp_fund_ledger.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("entry_no", name="uq_erp_fund_ledger_no"),
        sa.UniqueConstraint("idempotency_key", name="uq_erp_fund_ledger_idempotency"), comment="不可变资金流水", **OPTIONS)
    for column in ("entry_no", "idempotency_key", "entry_type", "account_id", "source_type", "source_id", "reversal_of_id", "occurred_at"):
        op.create_index(f"ix_erp_fund_ledger_{column}", "erp_fund_ledger", [column])

    with op.batch_alter_table("erp_sales_receipt") as batch:
        batch.add_column(sa.Column("fund_account_id", sa.Integer()))
        batch.create_foreign_key("fk_erp_sales_receipt_fund_account", "erp_fund_account", ["fund_account_id"], ["id"])
        batch.create_index("ix_erp_sales_receipt_fund_account_id", ["fund_account_id"])
    with op.batch_alter_table("erp_purchase_payment") as batch:
        batch.add_column(sa.Column("fund_account_id", sa.Integer()))
        batch.create_foreign_key("fk_erp_purchase_payment_fund_account", "erp_fund_account", ["fund_account_id"], ["id"])
        batch.create_index("ix_erp_purchase_payment_fund_account_id", ["fund_account_id"])

    op.create_table("erp_settlement_document", *base(), sa.Column("document_no", sa.String(50), nullable=False),
        sa.Column("writeoff_type", sa.String(30), nullable=False), sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("customer_id", sa.Integer()), sa.Column("supplier_id", sa.Integer()),
        sa.Column("source_receipt_id", sa.Integer()), sa.Column("source_payment_id", sa.Integer()),
        sa.Column("amount", sa.DECIMAL(20, 4), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("posting_version", sa.Integer(), nullable=False, server_default="0"), sa.Column("created_by_id", sa.Integer()),
        sa.Column("approved_by_id", sa.Integer()), sa.Column("approved_at", sa.DateTime()), sa.Column("remark", sa.String(500)),
        sa.ForeignKeyConstraint(["customer_id"], ["erp_customer.id"]), sa.ForeignKeyConstraint(["supplier_id"], ["erp_supplier.id"]),
        sa.ForeignKeyConstraint(["source_receipt_id"], ["erp_sales_receipt.id"]),
        sa.ForeignKeyConstraint(["source_payment_id"], ["erp_purchase_payment.id"]),
        sa.UniqueConstraint("document_no", name="uq_erp_settlement_document_no"), comment="财务核销单", **OPTIONS)
    for column in ("document_no", "writeoff_type", "business_date", "status"):
        op.create_index(f"ix_erp_settlement_document_{column}", "erp_settlement_document", [column])
    op.create_table("erp_settlement_allocation", *base(), sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=False), sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.DECIMAL(20, 4), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["erp_settlement_document.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "target_type", "target_id", name="uq_erp_settlement_allocation"), comment="财务核销明细", **OPTIONS)
    op.create_index("ix_erp_settlement_allocation_document_id", "erp_settlement_allocation", ["document_id"])
    op.create_index("ix_erp_settlement_allocation_target_id", "erp_settlement_allocation", ["target_id"])
    install_menus()


def install_menus():
    """安装资金、核销、会计期间和经营利润页面权限。"""

    bind = op.get_bind()
    root = bind.execute(sa.text("SELECT id FROM vadmin_auth_menu WHERE path='/erp' AND is_delete=0 LIMIT 1")).scalar()
    if not root:
        return
    menu = sa.table("vadmin_auth_menu", *[sa.column(x, sa.String if x in {"title", "icon", "redirect", "component", "path", "menu_type", "perms"} else sa.Integer if x in {"order", "parent_id"} else sa.Boolean) for x in ("title", "icon", "redirect", "component", "path", "disabled", "hidden", "order", "menu_type", "parent_id", "perms", "noCache", "breadcrumb", "affix", "noTagsView", "canTo", "alwaysShow", "is_delete")])
    def add(title, parent, kind, order, perms, path=None, component=None, icon=None):
        """插入页面或按钮权限。"""

        return bind.execute(menu.insert().values(title=title, icon=icon, redirect=None, component=component, path=path, disabled=False, hidden=False, order=order, menu_type=kind, parent_id=parent, perms=perms, noCache=False, breadcrumb=True, affix=False, noTagsView=False, canTo=False, alwaysShow=False, is_delete=False)).lastrowid
    pages = (
        ("资金管理", "fund", "finance-funds", "views/Erp/Finance/Funds", 40, ("view", "create", "update", "delete", "approve", "unapprove")),
        ("财务核销", "settlement", "finance-settlements", "views/Erp/Finance/Settlements", 41, ("view", "create", "update", "delete", "approve", "unapprove")),
        ("会计期间", "period", "accounting-periods", "views/Erp/Finance/Periods", 42, ("create", "close", "reopen")),
        ("经营利润", "profit", "operating-profit", "views/Erp/Finance/Profit", 43, ()),
    )
    for title, code, path, component, order, actions in pages:
        page = add(title, root, "1", order, f"erp.finance.{code}.list", path, component, "ep:coin")
        for index, action in enumerate(actions):
            add(action, page, "2", index, f"erp.finance.{code}.{action}")


def downgrade():
    """移除财务菜单、关联列和财务表。"""

    op.get_bind().execute(sa.text("DELETE FROM vadmin_auth_menu WHERE perms LIKE 'erp.finance.%'"))
    op.drop_table("erp_settlement_allocation")
    op.drop_table("erp_settlement_document")
    with op.batch_alter_table("erp_purchase_payment") as batch:
        batch.drop_index("ix_erp_purchase_payment_fund_account_id")
        batch.drop_constraint("fk_erp_purchase_payment_fund_account", type_="foreignkey")
        batch.drop_column("fund_account_id")
    with op.batch_alter_table("erp_sales_receipt") as batch:
        batch.drop_index("ix_erp_sales_receipt_fund_account_id")
        batch.drop_constraint("fk_erp_sales_receipt_fund_account", type_="foreignkey")
        batch.drop_column("fund_account_id")
    for table in ("erp_fund_ledger", "erp_fund_document", "erp_fund_account_balance", "erp_fund_account", "erp_accounting_period"):
        op.drop_table(table)
