"""Add fund account management and sales delivery batch mode.

Revision ID: f74c5b20e831
Revises: e63b4a19d720
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "f74c5b20e831"
down_revision = "e63b4a19d720"
branch_labels = None
depends_on = None


def _tables():
    """声明迁移所需的菜单和角色菜单轻量表。"""

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
    role_menu = sa.table(
        "vadmin_auth_role_menus",
        sa.column("role_id", sa.Integer),
        sa.column("menu_id", sa.Integer),
    )
    return menu, role_menu


def _insert_menu(bind, menu, **values) -> int:
    """插入标准页面或按钮菜单并返回主键。"""

    defaults = dict(
        icon=None,
        redirect=None,
        component=None,
        path=None,
        disabled=False,
        hidden=False,
        noCache=False,
        breadcrumb=True,
        affix=False,
        noTagsView=False,
        canTo=False,
        alwaysShow=False,
        is_delete=False,
    )
    defaults.update(values)
    return bind.execute(menu.insert().values(**defaults)).lastrowid


def _grant_like(bind, menu, role_menu, target_id: int, source_permission: str):
    """将旧资金权限对应的角色授权继承到新账户权限。"""

    source_ids = list(
        bind.execute(
            sa.select(menu.c.id).where(
                menu.c.perms == source_permission,
                menu.c.is_delete == sa.false(),
            )
        ).scalars()
    )
    if not source_ids:
        return
    role_ids = list(
        bind.execute(
            sa.select(sa.distinct(role_menu.c.role_id)).where(role_menu.c.menu_id.in_(source_ids))
        ).scalars()
    )
    for role_id in role_ids:
        exists = bind.execute(
            sa.select(role_menu.c.role_id).where(
                role_menu.c.role_id == role_id,
                role_menu.c.menu_id == target_id,
            )
        ).scalar()
        if exists is None:
            bind.execute(role_menu.insert().values(role_id=role_id, menu_id=target_id))


def _install_account_menu():
    """在财务管理下安装独立资金账户页面和权限。"""

    bind = op.get_bind()
    menu, role_menu = _tables()
    finance_group_id = bind.execute(
        sa.select(menu.c.id).where(
            menu.c.path == "finance-center",
            menu.c.menu_type == "0",
            menu.c.is_delete == sa.false(),
        )
    ).scalar()
    if finance_group_id is None:
        return

    bind.execute(
        menu.update()
        .where(menu.c.parent_id == finance_group_id, menu.c.menu_type == "1")
        .values(order=menu.c.order + 1)
    )
    page_id = _insert_menu(
        bind,
        menu,
        title="资金账户",
        icon="ep:credit-card",
        component="views/Erp/Finance/Accounts",
        path="fund-accounts",
        order=1,
        menu_type="1",
        parent_id=finance_group_id,
        perms="erp.finance.account.list",
    )
    create_id = _insert_menu(
        bind,
        menu,
        title="新增账户",
        order=1,
        menu_type="2",
        parent_id=page_id,
        perms="erp.finance.account.create",
    )
    update_id = _insert_menu(
        bind,
        menu,
        title="修改账户",
        order=2,
        menu_type="2",
        parent_id=page_id,
        perms="erp.finance.account.update",
    )
    _grant_like(bind, menu, role_menu, page_id, "erp.finance.fund.list")
    _grant_like(bind, menu, role_menu, create_id, "erp.finance.fund.create")
    _grant_like(bind, menu, role_menu, update_id, "erp.finance.fund.update")


def upgrade():
    """增加批次模式字段，并启用独立资金账户管理。"""

    op.add_column(
        "erp_sales_delivery",
        sa.Column(
            "batch_selection_mode",
            sa.String(20),
            nullable=False,
            server_default="auto",
            comment="批次选择模式：auto/manual",
        ),
    )
    op.execute(
        sa.text(
            "UPDATE erp_sales_delivery SET batch_selection_mode='manual' "
            "WHERE batch_selection_mode='auto'"
        )
    )
    _install_account_menu()


def downgrade():
    """移除账户菜单并恢复财务页面排序和销售出库表结构。"""

    bind = op.get_bind()
    menu, role_menu = _tables()
    ids = list(
        bind.execute(
            sa.select(menu.c.id).where(menu.c.perms.like("erp.finance.account.%"))
        ).scalars()
    )
    if ids:
        page_id = bind.execute(
            sa.select(menu.c.id).where(menu.c.perms == "erp.finance.account.list")
        ).scalar()
        finance_group_id = bind.execute(
            sa.select(menu.c.parent_id).where(menu.c.id == page_id)
        ).scalar()
        bind.execute(role_menu.delete().where(role_menu.c.menu_id.in_(ids)))
        bind.execute(menu.delete().where(menu.c.id.in_(ids)))
        if finance_group_id is not None:
            bind.execute(
                menu.update()
                .where(menu.c.parent_id == finance_group_id, menu.c.menu_type == "1")
                .values(order=menu.c.order - 1)
            )
    op.drop_column("erp_sales_delivery", "batch_selection_mode")
