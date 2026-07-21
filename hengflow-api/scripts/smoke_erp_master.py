"""Transaction-only smoke test for ERP master data; no test rows are committed."""
import asyncio
from uuid import uuid4

from apps.erp.master import models, schemas
from apps.erp.master.crud import MasterDal
from apps.erp.master.services import ProductSpuService
from core.database import async_engine, session_factory


async def run():
    async with session_factory() as session:
        token = uuid4().hex[:12].upper()
        category = await MasterDal(session, models.ErpProductCategory).create_data(
            schemas.ProductCategory(code=f"TEST_CAT_{token}", name="Smoke category").model_dump()
        )
        unit = await MasterDal(session, models.ErpUnit).create_data(
            schemas.Unit(code=f"TEST_UNIT_{token}", name="Smoke unit").model_dump()
        )
        child_unit = await MasterDal(session, models.ErpUnit).create_data(
            schemas.Unit(code=f"TEST_CHILD_{token}", name="Smoke child unit").model_dump()
        )
        leaf_unit = await MasterDal(session, models.ErpUnit).create_data(
            schemas.Unit(code=f"TEST_LEAF_{token}", name="Smoke leaf unit").model_dump()
        )
        group_dal = MasterDal(session, models.ErpUnitGroup)
        group_data = schemas.UnitGroup(
            name=f"Smoke group {token}", primary_unit_id=unit["id"]
        ).model_dump()
        await group_dal.ensure_unique(group_data)
        await group_dal.ensure_unit_group(group_data)
        group = await group_dal.create_data(group_data)
        item_dal = MasterDal(session, models.ErpUnitGroupItem)
        child_data = schemas.UnitGroupItem(
            group_id=group["id"], unit_id=child_unit["id"], factor=10
        ).model_dump()
        await item_dal.ensure_group_item(child_data)
        child = await item_dal.create_data(child_data)
        leaf_data = schemas.UnitGroupItem(
            group_id=group["id"], unit_id=leaf_unit["id"], parent_id=child["id"], factor=10
        ).model_dump()
        await item_dal.ensure_group_item(leaf_data)
        await item_dal.create_data(leaf_data)
        product = await ProductSpuService(session).save(schemas.ProductSpuInput(
            code=f"TEST_PRODUCT_{token}", name="Smoke product", category_id=category["id"],
            skus=[schemas.ProductSkuInput(
                code=f"TEST_SKU_{token}", multi_unit_enabled=True,
                unit_group_id=group["id"], is_default_sku=True,
            )],
        ))
        rows, count = await ProductSpuService(session).list(
            1, 10, f"TEST_PRODUCT_{token}", True
        )
        print(
            "crud smoke",
            product["skus"][0]["code"],
            count,
            len(rows),
            product["skus"][0]["base_unit_id"] == unit["id"],
        )
        await session.rollback()
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
