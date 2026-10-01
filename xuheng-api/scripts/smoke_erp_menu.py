"""ERP 分域菜单层级和角色权限继承冒烟测试。"""

import asyncio

from sqlalchemy import false, select

from apps.vadmin.auth.crud import MenuDal
from apps.vadmin.auth.models import VadminMenu, vadmin_auth_role_menus
from core.database import async_engine, session_factory


EXPECTED = {
    "master-data": 9,
    "purchase-center": 4,
    "sales-center": 4,
    "inventory-center": 5,
    "production-center": 2,
    "finance-center": 4,
}


async def run():
    """校验 ERP 根节点、六个功能域、页面归属和普通角色可见性。"""

    async with session_factory() as db:
        root = await db.scalar(select(VadminMenu).where(
            VadminMenu.path == "/erp",
            VadminMenu.menu_type == "0",
            VadminMenu.is_delete == false(),
        ))
        assert root is not None
        groups = list((await db.scalars(select(VadminMenu).where(
            VadminMenu.parent_id == root.id,
            VadminMenu.menu_type == "0",
            VadminMenu.is_delete == false(),
        ).order_by(VadminMenu.order))).all())
        assert [group.path for group in groups] == list(EXPECTED)
        assert root.redirect == "/erp/master-data/products"

        route_menus = [root, *groups]
        for group in groups:
            pages = list((await db.scalars(select(VadminMenu).where(
                VadminMenu.parent_id == group.id,
                VadminMenu.menu_type == "1",
                VadminMenu.is_delete == false(),
            ).order_by(VadminMenu.order))).all())
            assert len(pages) == EXPECTED[group.path]
            assert all(page.component and page.component.startswith("views/Erp/") for page in pages)
            route_menus.extend(pages)

            roles_with_pages = set((await db.scalars(select(vadmin_auth_role_menus.c.role_id).where(
                vadmin_auth_role_menus.c.menu_id.in_([page.id for page in pages])
            ))).all())
            roles_with_group = set((await db.scalars(select(vadmin_auth_role_menus.c.role_id).where(
                vadmin_auth_role_menus.c.menu_id == group.id
            ))).all())
            assert roles_with_pages <= roles_with_group

        routers = MenuDal(db).generate_router_tree(route_menus, iter([root]))
        assert len(routers) == 1 and len(routers[0]["children"]) == len(EXPECTED)
        assert all(len(group["children"]) == EXPECTED[group["path"]] for group in routers[0]["children"])
        print("ERP menu smoke: master -> purchase -> sales -> inventory -> production -> finance OK")
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
