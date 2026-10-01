"""采购订单到付款完整事务冒烟测试。"""

import asyncio
from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from apps.erp.inventory import models as inventory_models
from apps.erp.finance import models as finance_models
from apps.erp.master import models as master
from apps.erp.purchase import models, schemas
from apps.erp.purchase.services import PurchaseOrderService, PurchasePaymentService, PurchaseReceiptService, PurchaseReturnService
from core.database import async_engine, session_factory
from scripts.erp_factories import create_product


async def run():
    """验证分批收货、退货、应付、付款和完整倒序冲销。"""

    async with session_factory() as session:
        token = uuid4().hex[:8].upper()
        category = master.ErpProductCategory(code=f"P_CAT_{token}", name="Purchase category")
        unit = master.ErpUnit(code=f"P_UNIT_{token}", name="件", decimal_places=0)
        warehouse = master.ErpWarehouse(code=f"P_WH_{token}", name="Purchase warehouse")
        supplier = master.ErpSupplier(code=f"P_SUP_{token}", name="Purchase supplier", payment_days=30)
        settlement = master.ErpSettlementMethod(code=f"P_PAY_{token}", name="Bank")
        session.add_all([category, unit, warehouse, supplier, settlement])
        await session.flush()
        fund_account = finance_models.ErpFundAccount(code=f"P_FUND_{token}", name="Purchase fund")
        session.add(fund_account)
        await session.flush()
        product = await create_product(
            session, master, code=f"P_PROD_{token}", name="Purchase product",
            category_id=category.id, base_unit_id=unit.id, default_purchase_price=5, tax_rate=10,
        )

        order_service = PurchaseOrderService(session, 1)
        order = await order_service.save(schemas.PurchaseOrderInput(
            business_date=date.today(), supplier_id=supplier.id, warehouse_id=warehouse.id,
            lines=[schemas.PurchaseLineInput(product_id=product.id, unit_id=unit.id, quantity=10, unit_price=5, tax_rate=10)],
        ))
        order = await order_service.approve(order["id"])
        order_line_id = order["lines"][0]["id"]

        receipt_service = PurchaseReceiptService(session, 1)
        receipts = []
        for quantity in (6, 4):
            receipt = await receipt_service.save(schemas.PurchaseReceiptInput(
                business_date=date.today(), supplier_id=supplier.id, warehouse_id=warehouse.id,
                order_id=order["id"], lines=[schemas.PurchaseLineInput(
                    product_id=product.id, unit_id=unit.id, quantity=quantity, unit_price=5,
                    tax_rate=10, order_line_id=order_line_id,
                )],
            ))
            receipts.append(await receipt_service.approve(receipt["id"]))
        order = await order_service.detail(models.ErpPurchaseOrder, models.ErpPurchaseOrderLine, "order_id", order["id"])
        assert order["status"] == "completed" and Decimal(str(order["lines"][0]["received_quantity"])) == Decimal("10")
        assert order["lines"][0]["product"]["code"] == product.code
        assert "variant_name" in order["lines"][0]["product"]

        balance = await session.scalar(select(inventory_models.ErpInventoryBalance).where(
            inventory_models.ErpInventoryBalance.warehouse_id == warehouse.id,
            inventory_models.ErpInventoryBalance.product_id == product.id,
        ))
        payable_balance = await session.scalar(select(models.ErpSupplierPayableBalance).where(models.ErpSupplierPayableBalance.supplier_id == supplier.id))
        assert balance.quantity == Decimal("10") and balance.average_cost == Decimal("5")
        assert payable_balance.amount == Decimal("55")

        first_line = receipts[0]["lines"][0]
        return_service = PurchaseReturnService(session, 1)
        purchase_return = await return_service.save(schemas.PurchaseReturnInput(
            business_date=date.today(), receipt_id=receipts[0]["id"], supplier_id=supplier.id,
            warehouse_id=warehouse.id, lines=[schemas.PurchaseLineInput(
                product_id=product.id, unit_id=unit.id, quantity=2, unit_price=5,
                tax_rate=10, receipt_line_id=first_line["id"],
            )],
        ))
        purchase_return = await return_service.approve(purchase_return["id"])
        assert balance.quantity == Decimal("8") and payable_balance.amount == Decimal("44")

        payable = await session.scalar(select(models.ErpPayable).where(models.ErpPayable.receipt_id == receipts[0]["id"]))
        payment_service = PurchasePaymentService(session, 1)
        payment = await payment_service.save(schemas.PurchasePaymentInput(
            payment_date=date.today(), supplier_id=supplier.id, settlement_method_id=settlement.id,
            fund_account_id=fund_account.id,
            amount=20, allocations=[schemas.PaymentAllocationInput(payable_id=payable.id, amount=20)],
        ))
        payment = await payment_service.approve(payment["id"])
        assert payable_balance.amount == Decimal("24") and payable.outstanding_amount == Decimal("2")

        await payment_service.unapprove(payment["id"])
        await return_service.unapprove(purchase_return["id"])
        await receipt_service.unapprove(receipts[1]["id"])
        await receipt_service.unapprove(receipts[0]["id"])
        reapproved = await receipt_service.approve(receipts[0]["id"])
        assert reapproved["posting_version"] == 2 and payable_balance.amount == Decimal("33")
        await receipt_service.unapprove(receipts[0]["id"])
        await order_service.unapprove(order["id"])
        assert balance.quantity == Decimal("0") and payable_balance.amount == Decimal("0")
        print("purchase smoke: order -> partial receipts -> return -> payable -> payment -> full reversal OK")
        await session.rollback()
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
