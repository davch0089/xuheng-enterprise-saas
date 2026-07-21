"""商品 SPU/SKU、独立库存和成本事务冒烟测试。"""

import asyncio
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from apps.erp.inventory import models as inventory_models
from apps.erp.inventory.services.inbound import InventoryService
from apps.erp.inventory.services.stock import MovementType, PostingRequest, StockMovement, StockPostingEngine
from apps.erp.master import models, schemas
from apps.erp.master.services import ProductSpuService
from core.database import async_engine, session_factory
from core.exception import CustomException


async def run():
    """验证同一 SPU 的两个 SKU 能按条码独立搜索、库存和计价。"""

    async with session_factory() as session:
        token = uuid4().hex[:8].upper()
        category = models.ErpProductCategory(code=f"SKU_CAT_{token}", name="SKU category")
        unit = models.ErpUnit(code=f"SKU_UNIT_{token}", name="件", decimal_places=0)
        warehouse = models.ErpWarehouse(code=f"SKU_WH_{token}", name="SKU warehouse")
        session.add_all([category, unit, warehouse])
        await session.flush()

        service = ProductSpuService(session)
        product_input = schemas.ProductSpuInput(
            code=f"SPU_{token}",
            name="测试T恤",
            category_id=category.id,
            skus=[
                schemas.ProductSkuInput(
                    code=f"SKU_RED_M_{token}", barcode=f"BAR_RED_M_{token}",
                    base_unit_id=unit.id, is_default_sku=True,
                    attributes=[
                        schemas.ProductSkuAttributeInput(name="颜色", value="红色"),
                        schemas.ProductSkuAttributeInput(name="尺寸", value="M"),
                    ],
                ),
                schemas.ProductSkuInput(
                    code=f"SKU_BLUE_L_{token}", barcode=f"BAR_BLUE_L_{token}",
                    base_unit_id=unit.id,
                    attributes=[
                        schemas.ProductSkuAttributeInput(name="尺寸", value="L"),
                        schemas.ProductSkuAttributeInput(name="颜色", value="蓝色"),
                    ],
                ),
            ],
        )
        spu = await service.save(product_input)
        assert len(spu["skus"]) == 2
        first, second = spu["skus"]
        assert first["spu_id"] == second["spu_id"] == spu["id"]
        assert first["barcode"] != second["barcode"]
        edited_input = product_input.model_copy(update={
            "skus": [
                sku.model_copy(update={"id": saved["id"]})
                for sku, saved in zip(product_input.skus, (first, second))
            ]
        })
        edited = await service.save(edited_input, spu["id"])
        assert {item["variant_key"] for item in edited["skus"]} == {
            first["variant_key"], second["variant_key"]
        }

        plain_input = schemas.ProductSpuInput(
            code=f"SPU_PLAIN_{token}", name="无属性多SKU", category_id=category.id,
            skus=[
                schemas.ProductSkuInput(
                    code=f"SKU_PLAIN_A_{token}", base_unit_id=unit.id, is_default_sku=True
                ),
                schemas.ProductSkuInput(code=f"SKU_PLAIN_B_{token}", base_unit_id=unit.id),
            ],
        )
        plain = await service.save(plain_input)
        assert len({item["variant_key"] for item in plain["skus"]}) == 2
        plain_edited = await service.save(plain_input.model_copy(update={
            "skus": [
                sku.model_copy(update={"id": saved["id"]})
                for sku, saved in zip(plain_input.skus, plain["skus"])
            ]
        }), plain["id"])
        assert len(plain_edited["skus"]) == 2
        duplicate_attributes = [schemas.ProductSkuAttributeInput(name="颜色", value="黑色")]
        try:
            await service.save(schemas.ProductSpuInput(
                code=f"SPU_DUP_{token}", name="重复规格测试", category_id=category.id,
                skus=[
                    schemas.ProductSkuInput(
                        code=f"SKU_DUP_A_{token}", base_unit_id=unit.id,
                        attributes=duplicate_attributes, is_default_sku=True,
                    ),
                    schemas.ProductSkuInput(
                        code=f"SKU_DUP_B_{token}", base_unit_id=unit.id,
                        attributes=duplicate_attributes,
                    ),
                ],
            ))
            raise AssertionError("相同结构化规格组合应被拒绝")
        except CustomException as error:
            assert "规格组合重复" in str(error)

        await StockPostingEngine(session).post(PostingRequest(
            source_type="sku_smoke", source_id=1, source_no=f"SKU-{token}", posting_version=1,
            movements=(
                StockMovement(MovementType.PURCHASE_IN, 1, first["id"], warehouse.id, Decimal("10"), amount=Decimal("100")),
                StockMovement(MovementType.PURCHASE_IN, 2, second["id"], warehouse.id, Decimal("5"), amount=Decimal("100")),
            ),
        ))
        balances = list((await session.scalars(select(inventory_models.ErpInventoryBalance).where(
            inventory_models.ErpInventoryBalance.product_id.in_((first["id"], second["id"]))
        ).order_by(inventory_models.ErpInventoryBalance.product_id))).all())
        by_product = {item.product_id: item for item in balances}
        assert by_product[first["id"]].quantity == Decimal("10")
        assert by_product[first["id"]].average_cost == Decimal("10")
        assert by_product[second["id"]].quantity == Decimal("5")
        assert by_product[second["id"]].average_cost == Decimal("20")

        scanned = await InventoryService(session).search_products(first["barcode"], warehouse.id, 10)
        grouped = await InventoryService(session).search_products(spu["code"], warehouse.id, 10)
        assert len(scanned) == 1 and scanned[0]["id"] == first["id"]
        assert first["code"] in scanned[0]["sku_label"]
        assert "红色" in scanned[0]["display_spec"] and "M" in scanned[0]["display_spec"]
        assert {item["id"] for item in grouped} == {first["id"], second["id"]}

        await StockPostingEngine(session).reverse("sku_smoke", 1, 1, f"SKU-{token}", None)
        assert by_product[first["id"]].quantity == Decimal("0")
        assert by_product[second["id"]].quantity == Decimal("0")
        try:
            await service.delete(spu["id"])
            raise AssertionError("产生库存历史的 SKU 不应允许删除")
        except CustomException as error:
            assert "不能删除" in str(error)
        print("SKU smoke: SPU -> two barcodes -> independent stock/cost -> scan -> reversal OK")
        await session.rollback()
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
