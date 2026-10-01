"""Transaction smoke test for serial lifecycle and BOM assembly/disassembly."""

import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from apps.erp.inventory import models
from apps.erp.inventory.assembly_schemas import AssemblyOrderInput, BomInput, BomLineInput
from apps.erp.inventory.schemas import InboundLineInput, InboundReceiptInput
from apps.erp.inventory.services.assembly import AssemblyOrderService, BomService
from apps.erp.inventory.services.inbound import InventoryService
from apps.erp.inventory.queries import InventoryQueryService
from apps.erp.inventory.services.stock import MovementType, PostingRequest, StockMovement, StockPostingEngine
from apps.erp.master import models as master
from core.database import async_engine, session_factory
from scripts.erp_factories import create_product


async def run():
    """Run F11/F12 posting and reversal scenarios without committing rows."""

    async with session_factory() as session:
        token = uuid4().hex[:8].upper()
        category = master.ErpProductCategory(code=f"BOM_CAT_{token}", name="BOM category")
        unit = master.ErpUnit(code=f"BOM_UNIT_{token}", name="件", decimal_places=0)
        warehouse = master.ErpWarehouse(code=f"BOM_WH_{token}", name="BOM warehouse")
        session.add_all([category, unit, warehouse]); await session.flush()
        component = await create_product(session, master, code=f"COMP_{token}", name="Component", category_id=category.id, base_unit_id=unit.id)
        finished = await create_product(session, master, code=f"FIN_{token}", name="Finished", category_id=category.id, base_unit_id=unit.id)
        serial_product = await create_product(session, master, code=f"SER_{token}", name="Serial product", category_id=category.id, base_unit_id=unit.id, serial_enabled=True)
        batch_product = await create_product(session, master, code=f"BAT_{token}", name="Batch product", category_id=category.id, base_unit_id=unit.id, batch_enabled=True)
        inbound_service = InventoryService(session)
        component_in = await inbound_service.save_receipt(InboundReceiptInput(receipt_date=date.today(), business_type="other", warehouse_id=warehouse.id, lines=[InboundLineInput(product_id=component.id, unit_id=unit.id, quantity=10, unit_price=5)]))
        await inbound_service.approve(component_in["id"])
        serial_in = await inbound_service.save_receipt(InboundReceiptInput(receipt_date=date.today(), business_type="other", warehouse_id=warehouse.id, lines=[InboundLineInput(product_id=serial_product.id, unit_id=unit.id, quantity=1, unit_price=3, serial_numbers=[f"SN-{token}"])]))
        await inbound_service.approve(serial_in["id"])
        serial = await session.scalar(select(models.ErpInventorySerial).where(models.ErpInventorySerial.product_id == serial_product.id))
        assert await session.scalar(select(func.count(models.ErpInventorySerialMovement.id)).where(models.ErpInventorySerialMovement.serial_id == serial.id)) == 1
        serial_out = await StockPostingEngine(session).post(PostingRequest(
            source_type="tracking_smoke", source_id=serial_in["id"], source_no=f"TRACK-{token}", posting_version=1,
            occurred_at=datetime.now(), movements=(StockMovement(movement_type=MovementType.OTHER_OUT,
            business_line_id=serial_in["lines"][0]["id"], movement_role="serial_out", product_id=serial_product.id,
            warehouse_id=warehouse.id, quantity=Decimal("1"), serial_numbers=(f"SN-{token}",)),),
        ))
        assert serial.status == "outbound" and serial.warehouse_id is None
        await StockPostingEngine(session).reverse("tracking_smoke", serial_in["id"], 1, f"TRACK-{token}")
        assert serial.status == "in_stock" and serial.warehouse_id == warehouse.id
        await inbound_service.unapprove(serial_in["id"])
        assert await session.scalar(select(func.count(models.ErpInventorySerialMovement.id)).where(models.ErpInventorySerialMovement.serial_id == serial.id)) == 4

        batch_receipts = []
        for batch_no, quantity, expiry in ((f"LATE-{token}", 5, date.today() + timedelta(days=60)), (f"EARLY-{token}", 3, date.today() + timedelta(days=10))):
            receipt = await inbound_service.save_receipt(InboundReceiptInput(receipt_date=date.today(), business_type="other", warehouse_id=warehouse.id, lines=[InboundLineInput(product_id=batch_product.id, unit_id=unit.id, quantity=quantity, unit_price=2, batch_no=batch_no, expiry_date=expiry)]))
            await inbound_service.approve(receipt["id"])
            batch_receipts.append(receipt)
        allocation = await InventoryQueryService(session).fifo_batches(warehouse.id, batch_product.id, Decimal("6"))
        assert allocation["items"][0]["batch_no"] == f"EARLY-{token}"
        assert Decimal(str(allocation["items"][0]["suggested_quantity"])) == Decimal("3")
        assert Decimal(str(allocation["items"][1]["suggested_quantity"])) == Decimal("3")

        bom = await BomService(session).save(BomInput(code=f"BOM-{token}", name="Smoke BOM", product_id=finished.id, unit_id=unit.id, output_quantity=1, lines=[BomLineInput(component_product_id=component.id, unit_id=unit.id, quantity=2)]))
        service = AssemblyOrderService(session)
        assembly = await service.save(AssemblyOrderInput(business_date=date.today(), order_type="assembly", bom_id=bom["id"], warehouse_id=warehouse.id, quantity=2))
        assembly = await service.approve(assembly["id"])
        assert Decimal(str(assembly["finished_cost"])) == Decimal("20")
        component_balance = await session.scalar(select(models.ErpInventoryBalance).where(models.ErpInventoryBalance.warehouse_id == warehouse.id, models.ErpInventoryBalance.product_id == component.id))
        finished_balance = await session.scalar(select(models.ErpInventoryBalance).where(models.ErpInventoryBalance.warehouse_id == warehouse.id, models.ErpInventoryBalance.product_id == finished.id))
        assert component_balance.quantity == Decimal("6") and finished_balance.quantity == Decimal("2")

        disassembly = await service.save(AssemblyOrderInput(business_date=date.today(), order_type="disassembly", bom_id=bom["id"], warehouse_id=warehouse.id, quantity=1))
        await service.approve(disassembly["id"])
        assert component_balance.quantity == Decimal("8") and finished_balance.quantity == Decimal("1")
        await service.unapprove(disassembly["id"])
        await service.unapprove(assembly["id"])
        assert component_balance.quantity == Decimal("10") and finished_balance.quantity == Decimal("0")
        await inbound_service.unapprove(component_in["id"])
        for receipt in reversed(batch_receipts):
            await inbound_service.unapprove(receipt["id"])
        print("F11/F12 smoke: FEFO -> serial lifecycle -> assembly cost rollup -> disassembly allocation -> reversal OK")
        await session.rollback()
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
