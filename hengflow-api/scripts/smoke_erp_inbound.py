"""Transaction-only smoke test for inbound posting; no test rows are committed."""
import asyncio
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from apps.erp.inventory import models as inventory_models
from apps.erp.inventory.costing import (
    CostAdjustmentRequest,
    CostRevaluationRequest,
    InventoryCostEngine,
)
from apps.erp.inventory.crud import InventoryService
from apps.erp.inventory.posting import (
    MovementType,
    PostingRequest,
    StockMovement,
    StockPostingEngine,
)
from apps.erp.inventory.query import InventoryQueryService
from apps.erp.inventory.schemas import InboundLineInput, InboundReceiptInput
from apps.erp.master import models as master_models
from core.database import async_engine, session_factory
from scripts.erp_factories import create_product


async def run():
    async with session_factory() as session:
        token = uuid4().hex[:10].upper()
        category = master_models.ErpProductCategory(code=f"SMOKE_CAT_{token}", name="Smoke category")
        unit = master_models.ErpUnit(code=f"SMOKE_UNIT_{token}", name="箱", decimal_places=2)
        child_unit = master_models.ErpUnit(code=f"SMOKE_CHILD_{token}", name="袋", decimal_places=0)
        warehouse = master_models.ErpWarehouse(code=f"SMOKE_WH_{token}", name="Smoke warehouse")
        target_warehouse = master_models.ErpWarehouse(
            code=f"SMOKE_WH2_{token}", name="Smoke target warehouse"
        )
        session.add_all([category, unit, child_unit, warehouse, target_warehouse])
        await session.flush()
        unit_group = master_models.ErpUnitGroup(name=f"Smoke group {token}", primary_unit_id=unit.id)
        session.add(unit_group)
        await session.flush()
        session.add(
            master_models.ErpUnitGroupItem(
                group_id=unit_group.id,
                unit_id=child_unit.id,
                factor=Decimal("10"),
            )
        )
        product = await create_product(
            session,
            master_models,
            code=f"SMOKE_PRODUCT_{token}",
            name="Smoke product",
            category_id=category.id,
            base_unit_id=unit.id,
            multi_unit_enabled=True,
            unit_group_id=unit_group.id,
            default_purchase_price=Decimal("12.50"),
            batch_enabled=True,
            shelf_life_days=30,
        )
        serial_product = await create_product(
            session,
            master_models,
            code=f"SMOKE_SERIAL_{token}",
            name="Smoke serial product",
            category_id=category.id,
            base_unit_id=child_unit.id,
            serial_enabled=True,
            default_purchase_price=Decimal("3"),
        )

        service = InventoryService(session, user_id=None)
        receipt = await service.save_receipt(
            InboundReceiptInput(
                receipt_date=date.today(),
                business_type="other",
                warehouse_id=warehouse.id,
                lines=[
                    InboundLineInput(
                        product_id=product.id,
                        warehouse_id=warehouse.id,
                        unit_id=child_unit.id,
                        quantity=Decimal("20"),
                        unit_price=Decimal("1.25"),
                        batch_no="BATCH-001",
                        production_date=date.today(),
                    ),
                    InboundLineInput(
                        product_id=serial_product.id,
                        warehouse_id=warehouse.id,
                        unit_id=child_unit.id,
                        quantity=Decimal("2"),
                        unit_price=Decimal("3"),
                        serial_numbers=["SN-001", "SN-002"],
                    ),
                    InboundLineInput(
                        product_id=product.id,
                        warehouse_id=warehouse.id,
                        unit_id=child_unit.id,
                        quantity=Decimal("10"),
                        unit_price=Decimal("1.25"),
                        batch_no="BATCH-001",
                        production_date=date.today(),
                    ),
                ],
            )
        )
        await service.approve(receipt["id"])
        balance = await session.scalar(
            select(inventory_models.ErpInventoryBalance).where(
                inventory_models.ErpInventoryBalance.warehouse_id == warehouse.id,
                inventory_models.ErpInventoryBalance.product_id == product.id,
            )
        )
        assert balance.quantity == Decimal("3.000000")
        assert balance.average_cost == Decimal("12.500000")
        assert balance.inventory_value == Decimal("37.5000")
        cost_balance = await session.scalar(
            select(inventory_models.ErpInventoryCostBalance).where(
                inventory_models.ErpInventoryCostBalance.warehouse_id == warehouse.id,
                inventory_models.ErpInventoryCostBalance.product_id == product.id,
            )
        )
        assert cost_balance.quantity == Decimal("3.000000")
        assert cost_balance.average_cost == Decimal("12.500000")
        assert cost_balance.inventory_value == Decimal("37.5000")
        initial_cost_count = await session.scalar(
            select(func.count(inventory_models.ErpInventoryCostLedger.id)).where(
                inventory_models.ErpInventoryCostLedger.source_type == "inbound",
                inventory_models.ErpInventoryCostLedger.source_id == receipt["id"],
            )
        )
        assert initial_cost_count == 3
        batch = await session.scalar(
            select(inventory_models.ErpInventoryBatchBalance).where(
                inventory_models.ErpInventoryBatchBalance.product_id == product.id
            )
        )
        assert batch.quantity == Decimal("3.000000")
        assert batch.expiry_date == date.today() + timedelta(days=30)
        serial_count = await session.scalar(
            select(func.count(inventory_models.ErpInventorySerial.id)).where(
                inventory_models.ErpInventorySerial.product_id == serial_product.id
            )
        )
        assert serial_count == 2
        query = InventoryQueryService(session)
        stock_data, stock_count = await query.balances(
            1, 20, keyword=token, warehouse_id=warehouse.id
        )
        assert stock_count == 2
        assert len(stock_data["items"]) == 2
        assert Decimal(str(stock_data["summary"]["inventory_value"])) == Decimal("43.5")
        movement_data, movement_count = await query.movements(
            1, 20, keyword=receipt["receipt_no"], warehouse_id=warehouse.id
        )
        assert movement_count == 3
        assert len(movement_data) == 3
        batch_data, batch_count = await query.batches(
            1, 20, keyword="BATCH-001", warehouse_id=warehouse.id
        )
        assert batch_count == 1
        assert batch_data[0]["available_quantity"] == 3
        serial_data, serial_query_count = await query.serials(
            1, 20, keyword="SN-", warehouse_id=warehouse.id, status="in_stock"
        )
        assert serial_query_count == 2
        assert len(serial_data) == 2

        # A future outbound module only builds this request; it never updates stock itself.
        engine = StockPostingEngine(session)
        weighted_receipt_request = PostingRequest(
            source_type="smoke_weighted_receipt",
            source_id=receipt["id"],
            source_no=f"RK2-{token}",
            posting_version=1,
            movements=(
                StockMovement(
                    movement_type=MovementType.OTHER_IN,
                    business_line_id=89001,
                    movement_role="receipt",
                    product_id=product.id,
                    warehouse_id=warehouse.id,
                    quantity=Decimal("1"),
                    amount=Decimal("20"),
                    batch_no="BATCH-001",
                ),
            ),
        )
        weighted_ledgers = await engine.post(weighted_receipt_request)
        assert cost_balance.quantity == Decimal("4.000000")
        assert cost_balance.inventory_value == Decimal("57.5000")
        assert cost_balance.average_cost == Decimal("14.375000")
        weighted_cost_ledger = await session.scalar(
            select(inventory_models.ErpInventoryCostLedger).where(
                inventory_models.ErpInventoryCostLedger.stock_movement_id
                == weighted_ledgers[0].id
            )
        )
        assert weighted_cost_ledger is not None
        await engine.reverse(
            source_type="smoke_weighted_receipt",
            source_id=receipt["id"],
            posting_version=1,
            source_no=f"RK2-{token}",
        )
        assert cost_balance.quantity == Decimal("3.000000")
        assert cost_balance.inventory_value == Decimal("37.5000")
        assert cost_balance.average_cost == Decimal("12.500000")

        outbound_request = PostingRequest(
            source_type="smoke_outbound",
            source_id=receipt["id"],
            source_no=f"CK-{token}",
            posting_version=1,
            movements=(
                StockMovement(
                    movement_type=MovementType.OTHER_OUT,
                    business_line_id=90001,
                    movement_role="outbound",
                    product_id=product.id,
                    warehouse_id=warehouse.id,
                    quantity=Decimal("1"),
                    batch_no="BATCH-001",
                ),
                StockMovement(
                    movement_type=MovementType.OTHER_OUT,
                    business_line_id=90002,
                    movement_role="outbound",
                    product_id=serial_product.id,
                    warehouse_id=warehouse.id,
                    quantity=Decimal("1"),
                    serial_numbers=("SN-001",),
                ),
            ),
        )
        outbound_ledgers = await engine.post(outbound_request)
        assert balance.quantity == Decimal("2.000000")
        assert batch.quantity == Decimal("2.000000")
        # Replaying the same request is idempotent and returns the original ledgers.
        replayed = await engine.post(outbound_request)
        assert [item.id for item in replayed] == [item.id for item in outbound_ledgers]
        assert balance.quantity == Decimal("2.000000")
        outbound_cost_count = await session.scalar(
            select(func.count(inventory_models.ErpInventoryCostLedger.id)).where(
                inventory_models.ErpInventoryCostLedger.source_type == "smoke_outbound",
                inventory_models.ErpInventoryCostLedger.source_id == receipt["id"],
                inventory_models.ErpInventoryCostLedger.reversal_of_id.is_(None),
            )
        )
        assert outbound_cost_count == 2
        outbound_reversals = await engine.reverse(
            source_type="smoke_outbound",
            source_id=receipt["id"],
            posting_version=1,
            source_no=f"CK-{token}",
        )
        replayed_reversals = await engine.reverse(
            source_type="smoke_outbound",
            source_id=receipt["id"],
            posting_version=1,
            source_no=f"CK-{token}",
        )
        assert [item.id for item in replayed_reversals] == [
            item.id for item in outbound_reversals
        ]
        assert balance.quantity == Decimal("3.000000")
        assert batch.quantity == Decimal("3.000000")

        transfer_request = PostingRequest(
            source_type="smoke_transfer",
            source_id=receipt["id"],
            source_no=f"DB-{token}",
            posting_version=1,
            movements=(
                StockMovement(
                    MovementType.TRANSFER_OUT,
                    91001,
                    product.id,
                    warehouse.id,
                    Decimal("1"),
                    movement_role="transfer_out",
                    batch_no="BATCH-001",
                ),
                StockMovement(
                    MovementType.TRANSFER_IN,
                    91001,
                    product.id,
                    target_warehouse.id,
                    Decimal("1"),
                    movement_role="transfer_in",
                    batch_no="BATCH-001",
                ),
                StockMovement(
                    MovementType.TRANSFER_OUT,
                    91002,
                    serial_product.id,
                    warehouse.id,
                    Decimal("1"),
                    movement_role="transfer_out",
                    serial_numbers=("SN-002",),
                ),
                StockMovement(
                    MovementType.TRANSFER_IN,
                    91002,
                    serial_product.id,
                    target_warehouse.id,
                    Decimal("1"),
                    movement_role="transfer_in",
                    serial_numbers=("SN-002",),
                ),
            ),
        )
        await engine.post(transfer_request)
        target_balance = await session.scalar(
            select(inventory_models.ErpInventoryBalance).where(
                inventory_models.ErpInventoryBalance.warehouse_id == target_warehouse.id,
                inventory_models.ErpInventoryBalance.product_id == product.id,
            )
        )
        assert balance.quantity == Decimal("2.000000")
        assert target_balance.quantity == Decimal("1.000000")
        await engine.reverse(
            source_type="smoke_transfer",
            source_id=receipt["id"],
            posting_version=1,
            source_no=f"DB-{token}",
        )
        assert balance.quantity == Decimal("3.000000")
        assert target_balance.quantity == Decimal("0.000000")

        # Direct cost-only operations use InventoryCostEngine and keep the stock
        # balance cost mirror synchronized.
        cost_engine = InventoryCostEngine(session)
        adjustment = await cost_engine.adjust(
            CostAdjustmentRequest(
                idempotency_key=f"SMOKE:COST:ADJUST:{token}:V1",
                cost_no=f"COST-ADJ-{token}-V1",
                source_type="cost_adjustment",
                source_id=receipt["id"],
                source_no=f"TJ-{token}",
                posting_version=1,
                warehouse_id=warehouse.id,
                product_id=product.id,
                amount=Decimal("3"),
                remark="smoke cost adjustment",
            )
        )
        replayed_adjustment = await cost_engine.adjust(
            CostAdjustmentRequest(
                idempotency_key=f"SMOKE:COST:ADJUST:{token}:V1",
                cost_no=f"COST-ADJ-{token}-V1",
                source_type="cost_adjustment",
                source_id=receipt["id"],
                source_no=f"TJ-{token}",
                posting_version=1,
                warehouse_id=warehouse.id,
                product_id=product.id,
                amount=Decimal("3"),
            )
        )
        assert replayed_adjustment.ledger.id == adjustment.ledger.id
        assert cost_balance.inventory_value == Decimal("40.5000")
        assert cost_balance.average_cost == Decimal("13.500000")
        assert balance.inventory_value == Decimal("40.5000")
        revaluation = await cost_engine.revalue(
            CostRevaluationRequest(
                idempotency_key=f"SMOKE:COST:REVALUE:{token}:V1",
                cost_no=f"COST-REV-{token}-V1",
                source_type="cost_revaluation",
                source_id=receipt["id"],
                source_no=f"CJ-{token}",
                posting_version=1,
                warehouse_id=warehouse.id,
                product_id=product.id,
                target_average_cost=Decimal("14"),
            )
        )
        assert revaluation.signed_amount == Decimal("1.5000")
        assert cost_balance.inventory_value == Decimal("42.0000")
        assert balance.average_cost == Decimal("14.000000")
        await cost_engine.reverse_value_change(
            revaluation.ledger.id,
            source_type="cost_revaluation",
            source_id=receipt["id"],
            source_no=f"CJ-{token}",
            posting_version=1,
        )
        await cost_engine.reverse_value_change(
            adjustment.ledger.id,
            source_type="cost_adjustment",
            source_id=receipt["id"],
            source_no=f"TJ-{token}",
            posting_version=1,
        )
        assert cost_balance.inventory_value == Decimal("37.5000")
        assert cost_balance.average_cost == Decimal("12.500000")
        assert balance.inventory_value == Decimal("37.5000")

        immutable_cost_guard_triggered = False
        try:
            async with session.begin_nested():
                adjustment.ledger.remark = "ILLEGAL-CHANGE"
                await session.flush()
        except RuntimeError:
            immutable_cost_guard_triggered = True
        assert immutable_cost_guard_triggered
        await session.refresh(adjustment.ledger)

        immutable_guard_triggered = False
        try:
            async with session.begin_nested():
                outbound_ledgers[0].business_no = "ILLEGAL-CHANGE"
                await session.flush()
        except RuntimeError:
            immutable_guard_triggered = True
        assert immutable_guard_triggered
        await session.refresh(outbound_ledgers[0])

        await service.unapprove(receipt["id"])
        assert balance.quantity == Decimal("0.000000")
        assert balance.average_cost == Decimal("0.000000")
        assert balance.inventory_value == Decimal("0.0000")
        assert batch.quantity == Decimal("0.000000")
        serial_count = await session.scalar(
            select(func.count(inventory_models.ErpInventorySerial.id)).where(
                inventory_models.ErpInventorySerial.product_id == serial_product.id,
                inventory_models.ErpInventorySerial.status == "in_stock",
            )
        )
        assert serial_count == 0
        assert cost_balance.quantity == Decimal("0.000000")
        assert cost_balance.average_cost == Decimal("0.000000")
        assert cost_balance.inventory_value == Decimal("0.0000")
        print(
            "inventory smoke: stock posting + independent cost engine + reversal OK"
        )
        await session.rollback()
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
