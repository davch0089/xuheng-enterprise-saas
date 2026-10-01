"""Group ERP menus by business domain.

Revision ID: e63b4a19d720
Revises: d42f8a6b1c30
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "e63b4a19d720"
down_revision = "d42f8a6b1c30"
branch_labels = None
depends_on = None


GROUPS = (
    (
        "基础资料", "master-data", "ep:collection", "/erp/master-data/products", 10,
        (
            ("erp.master.product.list", "products"),
            ("erp.master.product_category.list", "product-categories"),
            ("erp.master.unit.list", "units"),
            ("erp.master.unit_conversion.list", "unit-conversions"),
            ("erp.master.customer.list", "customers"),
            ("erp.master.supplier.list", "suppliers"),
            ("erp.master.warehouse.list", "warehouses"),
            ("erp.master.employee.list", "employees"),
            ("erp.master.settlement_method.list", "settlement-methods"),
        ),
    ),
    (
        "采购管理", "purchase-center", "ep:shopping-cart", "/erp/purchase-center/purchase-orders", 20,
        (
            ("erp.purchase.order.list", "purchase-orders"),
            ("erp.purchase.receipt.list", "purchase-receipts"),
            ("erp.purchase.return.list", "purchase-returns"),
            ("erp.purchase.payable.list", "purchase-payables"),
        ),
    ),
    (
        "销售管理", "sales-center", "ep:sell", "/erp/sales-center/sales-orders", 30,
        (
            ("erp.sales.order.list", "sales-orders"),
            ("erp.sales.delivery.list", "sales-deliveries"),
            ("erp.sales.return.list", "sales-returns"),
            ("erp.sales.receipt.list", "sales-receivables"),
        ),
    ),
    (
        "库存管理", "inventory-center", "ep:box", "/erp/inventory-center/stocks", 40,
        (
            ("erp.inventory.stock.list", "stocks"),
            ("erp.inventory.inbound.list", "inbounds"),
            ("erp.inventory.transfer.list", "stock-transfers"),
            ("erp.inventory.count.list", "inventory-counts"),
            ("erp.inventory.other.list", "other-stock"),
        ),
    ),
    (
        "生产管理", "production-center", "ep:setting", "/erp/production-center/boms", 50,
        (
            ("erp.inventory.bom.list", "boms"),
            ("erp.inventory.assembly.list", "assembly-orders"),
        ),
    ),
    (
        "财务管理", "finance-center", "ep:wallet", "/erp/finance-center/finance-funds", 60,
        (
            ("erp.finance.fund.list", "finance-funds"),
            ("erp.finance.settlement.list", "finance-settlements"),
            ("erp.finance.period.list", "accounting-periods"),
            ("erp.finance.profit.list", "operating-profit"),
        ),
    ),
)


def _tables():
    """声明菜单和角色菜单关联表的轻量结构。"""

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


def _erp_root_id(bind, menu) -> int:
    """读取唯一的 ERP 根菜单，缺失时拒绝产生孤立分组。"""

    root_id = bind.execute(sa.select(menu.c.id).where(
        menu.c.path == "/erp", menu.c.menu_type == "0", menu.c.is_delete == sa.false()
    ).limit(1)).scalar()
    if root_id is None:
        raise RuntimeError("ERP root menu /erp does not exist")
    return root_id


def _save_group(bind, menu, root_id, title, path, icon, redirect, order) -> int:
    """新增或规范化一个 ERP 业务域分组。"""

    group_id = bind.execute(sa.select(menu.c.id).where(
        menu.c.parent_id == root_id,
        menu.c.path == path,
        menu.c.menu_type == "0",
        menu.c.is_delete == sa.false(),
    ).limit(1)).scalar()
    values = dict(
        title=title, icon=icon, redirect=redirect, component="##", path=path,
        disabled=False, hidden=False, order=order, menu_type="0", parent_id=root_id,
        perms=None, noCache=False, breadcrumb=True, affix=False, noTagsView=False,
        canTo=False, alwaysShow=True, is_delete=False,
    )
    if group_id is not None:
        bind.execute(menu.update().where(menu.c.id == group_id).values(**values))
        return group_id
    return bind.execute(menu.insert().values(**values)).lastrowid


def _inherit_role_access(bind, role_menu, group_id: int, page_ids: list[int]):
    """让原本拥有任一分组页面的角色同时拥有新的父级菜单。"""

    if not page_ids:
        return
    role_ids = list(bind.execute(sa.select(sa.distinct(role_menu.c.role_id)).where(
        role_menu.c.menu_id.in_(page_ids)
    )).scalars())
    for role_id in role_ids:
        exists = bind.execute(sa.select(role_menu.c.role_id).where(
            role_menu.c.role_id == role_id, role_menu.c.menu_id == group_id
        ).limit(1)).scalar()
        if exists is None:
            bind.execute(role_menu.insert().values(role_id=role_id, menu_id=group_id))


def upgrade():
    """创建业务域分组、移动页面并继承已有角色权限。"""

    bind = op.get_bind()
    menu, role_menu = _tables()
    root_id = _erp_root_id(bind, menu)
    bind.execute(menu.update().where(menu.c.id == root_id).values(
        redirect="/erp/master-data/products", alwaysShow=True
    ))
    for title, path, icon, redirect, group_order, pages in GROUPS:
        group_id = _save_group(bind, menu, root_id, title, path, icon, redirect, group_order)
        page_ids = []
        for page_order, (permission, page_path) in enumerate(pages, 1):
            page_id = bind.execute(sa.select(menu.c.id).where(
                menu.c.perms == permission,
                menu.c.menu_type == "1",
                menu.c.is_delete == sa.false(),
            ).limit(1)).scalar()
            if page_id is None:
                continue
            page_ids.append(page_id)
            bind.execute(menu.update().where(menu.c.id == page_id).values(
                parent_id=group_id, path=page_path, order=page_order
            ))
        _inherit_role_access(bind, role_menu, group_id, page_ids)


def downgrade():
    """移除业务域分组并把 ERP 页面恢复到根菜单下。"""

    bind = op.get_bind()
    menu, role_menu = _tables()
    root_id = _erp_root_id(bind, menu)
    original_order = 1
    group_ids = []
    for _title, path, _icon, _redirect, _group_order, pages in GROUPS:
        group_id = bind.execute(sa.select(menu.c.id).where(
            menu.c.parent_id == root_id, menu.c.path == path, menu.c.menu_type == "0"
        ).limit(1)).scalar()
        if group_id is not None:
            group_ids.append(group_id)
        for permission, page_path in pages:
            bind.execute(menu.update().where(
                menu.c.perms == permission, menu.c.menu_type == "1"
            ).values(parent_id=root_id, path=page_path, order=original_order))
            original_order += 1
    if group_ids:
        bind.execute(role_menu.delete().where(role_menu.c.menu_id.in_(group_ids)))
        bind.execute(menu.delete().where(menu.c.id.in_(group_ids)))
    bind.execute(menu.update().where(menu.c.id == root_id).values(redirect="/erp/products"))
