"""Transaction-only smoke test for the complete sales order-to-cash flow."""

import asyncio
from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from apps.erp.inventory import models as inventory_models
from apps.erp.finance import models as finance_models
from apps.erp.inventory.crud import InventoryService
from apps.erp.inventory.schemas import InboundLineInput, InboundReceiptInput
from apps.erp.master import models as master_models
from apps.erp.sales import models as sales_models
from apps.erp.sales.schemas import (
    SalesDeliveryInput,
    SalesLineInput,
    SalesOrderInput,
    SalesReceiptInput,
    SalesReturnInput,
)
from apps.erp.sales.schemas.documents import SalesReturnLineInput
from apps.erp.sales.services import (
    SalesDeliveryService,
    SalesOrderService,
    SalesReceiptService,
    SalesReturnService,
)
from core.database import async_engine, session_factory
from core.exception import CustomException
from scripts.erp_factories import create_product


async def run():
    """Create, post and reverse a full sales cycle without committing test rows."""

    async with session_factory() as session:
        token = uuid4().hex[:10].upper()
        category = master_models.ErpProductCategory(
            code=f"SALE_CAT_{token}", name="Sales smoke category"
        )
        unit = master_models.ErpUnit(code=f"SALE_UNIT_{token}", name="件")
        warehouse = master_models.ErpWarehouse(
            code=f"SALE_WH_{token}", name="Sales smoke warehouse"
        )
        customer = master_models.ErpCustomer(
            code=f"SALE_CUS_{token}",
            name="Sales smoke customer",
            payment_days=30,
            credit_limit=10000,
        )
        session.add_all([category, unit, warehouse, customer])
        await session.flush()
        fund_account = finance_models.ErpFundAccount(code=f"SALE_FUND_{token}", name="Sales fund")
        session.add(fund_account)
        await session.flush()
        product = await create_product(
            session,
            master_models,
            code=f"SALE_PRODUCT_{token}",
            name="Sales smoke product",
            category_id=category.id,
            base_unit_id=unit.id,
            default_purchase_price=5,
            default_sale_price=10,
            tax_rate=13,
        )

        inventory = InventoryService(session)
        inbound = await inventory.save_receipt(
            InboundReceiptInput(
                receipt_date=date.today(),
                business_type="other",
                warehouse_id=warehouse.id,
                lines=[
                    InboundLineInput(
                        product_id=product.id,
                        warehouse_id=warehouse.id,
                        unit_id=unit.id,
                        quantity=10,
                        unit_price=5,
                    )
                ],
            )
        )
        await inventory.approve(inbound["id"])

        order_service = SalesOrderService(session)
        order = await order_service.save(
            SalesOrderInput(
                business_date=date.today(),
                customer_id=customer.id,
                warehouse_id=warehouse.id,
                lines=[
                    SalesLineInput(
                        product_id=product.id,
                        warehouse_id=warehouse.id,
                        unit_id=unit.id,
                        quantity=6,
                        unit_price=10,
                        tax_rate=13,
                    )
                ],
            )
        )
        order_detail = await order_service.detail(order["id"])
        assert order_detail["lines"][0]["product"]["code"] == product.code
        assert "variant_name" in order_detail["lines"][0]["product"]
        await order_service.approve(order["id"])
        order_line = await session.scalar(
            select(sales_models.ErpSalesOrderLine).where(
                sales_models.ErpSalesOrderLine.order_id == order["id"]
            )
        )
        stock = await session.scalar(
            select(inventory_models.ErpInventoryBalance).where(
                inventory_models.ErpInventoryBalance.warehouse_id == warehouse.id,
                inventory_models.ErpInventoryBalance.product_id == product.id,
            )
        )
        assert stock.quantity == Decimal("10.000000")
        assert stock.reserved_quantity == Decimal("6.000000")
        assert stock.available_quantity == Decimal("4.000000")

        delivery_service = SalesDeliveryService(session)
        delivery = await delivery_service.save(
            SalesDeliveryInput(
                business_date=date.today(),
                customer_id=customer.id,
                warehouse_id=warehouse.id,
                order_id=order["id"],
                lines=[
                    SalesLineInput(
                        product_id=product.id,
                        warehouse_id=warehouse.id,
                        unit_id=unit.id,
                        quantity=4,
                        unit_price=10,
                        tax_rate=13,
                        order_line_id=order_line.id,
                    )
                ],
            )
        )
        delivery = await delivery_service.approve(delivery["id"])
        assert Decimal(str(delivery["total_cost"])) == Decimal("20")
        assert Decimal(str(delivery["gross_profit"])) == Decimal("20")
        assert stock.quantity == Decimal("6.000000")
        assert stock.reserved_quantity == Decimal("2.000000")
        assert stock.available_quantity == Decimal("4.000000")
        receivable = await session.scalar(
            select(sales_models.ErpReceivable).where(
                sales_models.ErpReceivable.delivery_id == delivery["id"]
            )
        )
        assert receivable.original_amount == Decimal("45.2000")

        delivery_line = await session.scalar(
            select(sales_models.ErpSalesDeliveryLine).where(
                sales_models.ErpSalesDeliveryLine.delivery_id == delivery["id"]
            )
        )
        return_service = SalesReturnService(session)
        sales_return = await return_service.save(
            SalesReturnInput(
                business_date=date.today(),
                delivery_id=delivery["id"],
                customer_id=customer.id,
                warehouse_id=warehouse.id,
                lines=[
                    SalesReturnLineInput(
                        delivery_line_id=delivery_line.id,
                        quantity=1,
                    )
                ],
            )
        )
        sales_return = await return_service.approve(sales_return["id"])
        assert stock.quantity == Decimal("7.000000")
        assert receivable.returned_amount == Decimal("11.3000")
        assert receivable.outstanding_amount == Decimal("33.9000")

        receipt_service = SalesReceiptService(session)
        receipt = await receipt_service.save(
            SalesReceiptInput(
                receipt_date=date.today(),
                customer_id=customer.id,
                fund_account_id=fund_account.id,
                amount=20,
            )
        )
        receipt = await receipt_service.approve(receipt["id"])
        assert receivable.settled_amount == Decimal("20.0000")
        assert receivable.outstanding_amount == Decimal("13.9000")
        customer_balance = await session.scalar(
            select(sales_models.ErpCustomerReceivableBalance).where(
                sales_models.ErpCustomerReceivableBalance.customer_id == customer.id
            )
        )
        assert customer_balance.amount == Decimal("13.9000")

        blocked = False
        try:
            await delivery_service.unapprove(delivery["id"])
        except CustomException:
            blocked = True
        assert blocked

        await receipt_service.unapprove(receipt["id"])
        await return_service.unapprove(sales_return["id"])
        await delivery_service.unapprove(delivery["id"])
        await order_service.unapprove(order["id"])
        await inventory.unapprove(inbound["id"])
        assert stock.quantity == Decimal("0.000000")
        assert stock.reserved_quantity == Decimal("0.000000")
        assert stock.available_quantity == Decimal("0.000000")
        assert customer_balance.amount == Decimal("0.0000")
        print("sales smoke: order -> reserve -> delivery -> return -> receipt -> reversal OK")
        await session.rollback()
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
