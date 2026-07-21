"""Inventory read models and stock menu.

Revision ID: e06b42a7f319
Revises: d95a31f6e208
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa


revision = "e06b42a7f319"
down_revision = "d95a31f6e208"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("erp_inventory_balance", "erp_inventory_batch_balance"):
        op.add_column(
            table,
            sa.Column(
                "reserved_quantity",
                sa.DECIMAL(20, 6),
                nullable=False,
                server_default="0",
                comment="已预留数量",
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "frozen_quantity",
                sa.DECIMAL(20, 6),
                nullable=False,
                server_default="0",
                comment="冻结数量",
            ),
        )
    _insert_menu()


def _insert_menu():
    bind = op.get_bind()
    root_id = bind.execute(
        sa.text("SELECT id FROM vadmin_auth_menu WHERE path='/erp' AND is_delete=0 LIMIT 1")
    ).scalar()
    if not root_id:
        return
    menu = sa.table(
        "vadmin_auth_menu",
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

    def add(title, parent_id, menu_type, order, perms, path=None, component=None, icon=None):
        result = bind.execute(
            menu.insert().values(
                title=title,
                icon=icon,
                redirect=None,
                component=component,
                path=path,
                disabled=False,
                hidden=False,
                order=order,
                menu_type=menu_type,
                parent_id=parent_id,
                perms=perms,
                noCache=False,
                breadcrumb=True,
                affix=False,
                noTagsView=False,
                canTo=False,
                alwaysShow=False,
                is_delete=False,
            )
        )
        return result.lastrowid

    page_id = add(
        "库存查询",
        root_id,
        "1",
        21,
        "erp.inventory.stock.list",
        path="stocks",
        component="views/Erp/Inventory/Stock",
        icon="ep:box",
    )
    add("查看", page_id, "2", 0, "erp.inventory.stock.view")


def downgrade():
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM vadmin_auth_menu WHERE perms IN ('erp.inventory.stock.list','erp.inventory.stock.view')"))
    for table in ("erp_inventory_batch_balance", "erp_inventory_balance"):
        op.drop_column(table, "frozen_quantity")
        op.drop_column(table, "reserved_quantity")
