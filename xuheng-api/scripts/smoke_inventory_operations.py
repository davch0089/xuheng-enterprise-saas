"""Transaction-only smoke test for transfer, count and other stock operations."""

import asyncio
from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from apps.erp.inventory import models
from apps.erp.inventory.operation_schemas import (
    InventoryCountInput,
    InventoryCountLineInput,
    OtherStockOrderInput,
    StockTransferInput,
    TrackedStockLineInput,
)
from apps.erp.inventory.schemas import InboundLineInput, InboundReceiptInput
from apps.erp.inventory.services.inbound import InventoryService
from apps.erp.inventory.services.operations import (
    InventoryCountService,
    OtherStockOrderService,
    StockTransferService,
)
from apps.erp.master import models as master_models
from core.database import async_engine, session_factory
from scripts.erp_factories import create_product


async def run():
    """Post and reverse every inventory operation without committing test data."""

    async with session_factory() as session:
        token = uuid4().hex[:8].upper()
        category = master_models.ErpProductCategory(code=f"OP_CAT_{token}", name="Operation category")
        unit = master_models.ErpUnit(code=f"OP_UNIT_{token}", name="件")
        source = master_models.ErpWarehouse(code=f"OP_SRC_{token}", name="Source warehouse")
        destination = master_models.ErpWarehouse(code=f"OP_DST_{token}", name="Destination warehouse")
        session.add_all([category, unit, source, destination])
        await session.flush()
        product = await create_product(
            session,
            master_models,
            code=f"OP_PRODUCT_{token}", name="Operation product",
            category_id=category.id, base_unit_id=unit.id, default_purchase_price=5,
        )

        inbound_service = InventoryService(session)
        inbound = await inbound_service.save_receipt(InboundReceiptInput(
            receipt_date=date.today(), business_type="other", warehouse_id=source.id,
            lines=[InboundLineInput(product_id=product.id, unit_id=unit.id, quantity=20, unit_price=5)],
        ))
        await inbound_service.approve(inbound["id"])

        async def quantities():
            """Read source and destination physical balances."""

            result = []
            for warehouse in (source, destination):
                value = await session.scalar(select(models.ErpInventoryBalance.quantity).where(
                    models.ErpInventoryBalance.warehouse_id == warehouse.id,
                    models.ErpInventoryBalance.product_id == product.id,
                ))
                result.append(Decimal(value or 0))
            return tuple(result)

        transfer_service = StockTransferService(session)
        one_step = await transfer_service.save(StockTransferInput(
            transfer_date=date.today(), transfer_mode="one_step",
            source_warehouse_id=source.id, destination_warehouse_id=destination.id,
            lines=[TrackedStockLineInput(product_id=product.id, unit_id=unit.id, quantity=3)],
        ))
        await transfer_service.dispatch(one_step["id"])
        assert await quantities() == (Decimal("17"), Decimal("3"))
        await transfer_service.undispatch(one_step["id"])
        assert await quantities() == (Decimal("20"), Decimal("0"))

        two_step = await transfer_service.save(StockTransferInput(
            transfer_date=date.today(), transfer_mode="two_step",
            source_warehouse_id=source.id, destination_warehouse_id=destination.id,
            lines=[TrackedStockLineInput(product_id=product.id, unit_id=unit.id, quantity=4)],
        ))
        await transfer_service.dispatch(two_step["id"])
        assert await quantities() == (Decimal("16"), Decimal("0"))
        await transfer_service.receive(two_step["id"])
        assert await quantities() == (Decimal("16"), Decimal("4"))
        await transfer_service.unreceive(two_step["id"])
        await transfer_service.undispatch(two_step["id"])
        assert await quantities() == (Decimal("20"), Decimal("0"))

        other_service = OtherStockOrderService(session)
        other_in = await other_service.save(OtherStockOrderInput(
            business_date=date.today(), direction="inbound", reason="Smoke gain",
            warehouse_id=source.id,
            lines=[TrackedStockLineInput(product_id=product.id, unit_id=unit.id, quantity=5, unit_price=6)],
        ))
        await other_service.approve(other_in["id"])
        other_out = await other_service.save(OtherStockOrderInput(
            business_date=date.today(), direction="outbound", reason="Smoke issue",
            warehouse_id=source.id,
            lines=[TrackedStockLineInput(product_id=product.id, unit_id=unit.id, quantity=2)],
        ))
        await other_service.approve(other_out["id"])
        assert await quantities() == (Decimal("23"), Decimal("0"))
        await other_service.unapprove(other_out["id"])
        await other_service.unapprove(other_in["id"])
        assert await quantities() == (Decimal("20"), Decimal("0"))

        count_service = InventoryCountService(session)
        count = await count_service.save(InventoryCountInput(
            count_date=date.today(), warehouse_id=source.id,
            lines=[InventoryCountLineInput(product_id=product.id, counted_quantity=18)],
        ))
        await count_service.approve(count["id"])
        assert await quantities() == (Decimal("18"), Decimal("0"))
        await count_service.unapprove(count["id"])
        assert await quantities() == (Decimal("20"), Decimal("0"))

        count = await count_service.save(InventoryCountInput(
            count_date=date.today(), warehouse_id=source.id,
            lines=[InventoryCountLineInput(product_id=product.id, counted_quantity=22)],
        ))
        await count_service.approve(count["id"])
        assert await quantities() == (Decimal("22"), Decimal("0"))
        await count_service.unapprove(count["id"])
        await inbound_service.unapprove(inbound["id"])
        assert await quantities() == (Decimal("0"), Decimal("0"))
        print("inventory operations smoke: one-step/two-step transfer -> other in/out -> gain/loss -> reversal OK")
        await session.rollback()
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
