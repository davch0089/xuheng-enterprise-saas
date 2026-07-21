"""资金、五类核销、期间控制和经营利润事务冒烟测试。"""

import asyncio
from datetime import date
from decimal import Decimal
from uuid import uuid4

from apps.erp.finance import models, schemas
from apps.erp.finance.services import AccountingPeriodService, FundDocumentService, ProfitQueryService, SettlementService
from apps.erp.master import models as master
from apps.erp.purchase import models as purchase_models, schemas as purchase_schemas
from apps.erp.purchase.services import PurchasePaymentService
from apps.erp.sales import models as sales_models, schemas as sales_schemas
from apps.erp.sales.services import SalesReceiptService
from core.database import async_engine, session_factory
from core.exception import CustomException


async def run():
    """验证收付转账、五类核销、冲销、期间关闭和利润口径。"""

    async with session_factory() as session:
        token = uuid4().hex[:8].upper()
        business_date = date(2099, 1, 15)
        category = master.ErpProductCategory(code=f"F_CAT_{token}", name="Finance category")
        unit = master.ErpUnit(code=f"F_UNIT_{token}", name="件")
        warehouse = master.ErpWarehouse(code=f"F_WH_{token}", name="Finance warehouse")
        customer = master.ErpCustomer(code=f"F_CUS_{token}", name="Finance customer")
        supplier = master.ErpSupplier(code=f"F_SUP_{token}", name="Finance supplier")
        session.add_all([category, unit, warehouse, customer, supplier])
        await session.flush()

        period_service = AccountingPeriodService(session, 1)
        period = await period_service.create(schemas.AccountingPeriodInput(
            period_code=f"2099-01-{token}", start_date=date(2099, 1, 1), end_date=date(2099, 1, 31)
        ))
        fund = FundDocumentService(session, 1)
        account_a = await fund.save_account(schemas.FundAccountInput(code=f"F_A_{token}", name="主账户", opening_balance=100))
        account_b = await fund.save_account(schemas.FundAccountInput(code=f"F_B_{token}", name="备用账户"))

        general_documents = []
        for document_type, amount, from_id, to_id, category_name in (
            ("receipt", 50, None, account_a["id"], "none"),
            ("payment", 10, account_a["id"], None, "variable_expense"),
            ("transfer", 20, account_a["id"], account_b["id"], "none"),
        ):
            document = await fund.save(schemas.FundDocumentInput(
                document_type=document_type, business_date=business_date, amount=amount,
                from_account_id=from_id, to_account_id=to_id, profit_category=category_name,
            ))
            general_documents.append(await fund.approve(document["id"]))

        sales_receipt_service = SalesReceiptService(session, 1)
        sales_receipt = await sales_receipt_service.save(sales_schemas.SalesReceiptInput(
            receipt_date=business_date, customer_id=customer.id, fund_account_id=account_a["id"], amount=30
        ))
        sales_receipt = await sales_receipt_service.approve(sales_receipt["id"])
        purchase_payment_service = PurchasePaymentService(session, 1)
        purchase_payment = await purchase_payment_service.save(purchase_schemas.PurchasePaymentInput(
            payment_date=business_date, supplier_id=supplier.id, fund_account_id=account_a["id"], amount=40
        ))
        purchase_payment = await purchase_payment_service.approve(purchase_payment["id"])

        delivery = sales_models.ErpSalesDelivery(
            delivery_no=f"F_SD_{token}", business_date=business_date, customer_id=customer.id,
            warehouse_id=warehouse.id, status="approved", total_amount=100, total_cost=60, gross_profit=40,
        )
        purchase_receipt = purchase_models.ErpPurchaseReceipt(
            receipt_no=f"F_PR_{token}", business_date=business_date, supplier_id=supplier.id,
            warehouse_id=warehouse.id, status="approved", total_amount=25, payable_amount=25,
        )
        session.add_all([delivery, purchase_receipt])
        await session.flush()
        receivable = sales_models.ErpReceivable(
            receivable_no=f"F_AR_{token}", customer_id=customer.id, delivery_id=delivery.id,
            delivery_no=delivery.delivery_no, business_date=business_date, original_amount=20,
            settled_amount=0, returned_amount=0, outstanding_amount=20, status="open",
        )
        payable = purchase_models.ErpPayable(
            payable_no=f"F_AP_{token}", supplier_id=supplier.id, receipt_id=purchase_receipt.id,
            receipt_no=purchase_receipt.receipt_no, business_date=business_date, original_amount=25,
            settled_amount=0, returned_amount=0, outstanding_amount=25, status="open",
        )
        session.add_all([receivable, payable])
        await session.flush()

        settlement = SettlementService(session, 1)
        advance_ar = await settlement.save(schemas.SettlementDocumentInput(
            writeoff_type="advance_receipt_ar", business_date=business_date, customer_id=customer.id,
            source_receipt_id=sales_receipt["id"], amount=10,
            allocations=[schemas.SettlementAllocationInput(target_type="receivable", target_id=receivable.id, amount=10)],
        ))
        advance_ar = await settlement.approve(advance_ar["id"])
        advance_ap = await settlement.save(schemas.SettlementDocumentInput(
            writeoff_type="advance_payment_ap", business_date=business_date, supplier_id=supplier.id,
            source_payment_id=purchase_payment["id"], amount=10,
            allocations=[schemas.SettlementAllocationInput(target_type="payable", target_id=payable.id, amount=10)],
        ))
        advance_ap = await settlement.approve(advance_ap["id"])
        offset = await settlement.save(schemas.SettlementDocumentInput(
            writeoff_type="ar_ap_offset", business_date=business_date, customer_id=customer.id,
            supplier_id=supplier.id, amount=5,
            allocations=[
                schemas.SettlementAllocationInput(target_type="receivable", target_id=receivable.id, amount=5),
                schemas.SettlementAllocationInput(target_type="payable", target_id=payable.id, amount=5),
            ],
        ))
        offset = await settlement.approve(offset["id"])
        assert receivable.outstanding_amount == Decimal("5") and payable.outstanding_amount == Decimal("10")

        sales_return = sales_models.ErpSalesReturn(
            return_no=f"F_SR_{token}", business_date=business_date, customer_id=customer.id,
            warehouse_id=warehouse.id, delivery_id=delivery.id, status="approved", total_amount=20, total_cost=12,
        )
        session.add(sales_return)
        await session.flush()
        profit = await ProfitQueryService(session).report(business_date, business_date)
        assert Decimal(str(profit["net_sales_revenue"])) == Decimal("80")
        assert Decimal(str(profit["sales_cost"])) == Decimal("48")
        assert Decimal(str(profit["gross_profit"])) == Decimal("32")
        assert Decimal(str(profit["contribution_profit"])) == Decimal("22")

        await settlement.unapprove(offset["id"])
        await settlement.unapprove(advance_ap["id"])
        await settlement.unapprove(advance_ar["id"])
        await sales_receipt_service.unapprove(sales_receipt["id"])
        await purchase_payment_service.unapprove(purchase_payment["id"])
        for document in reversed(general_documents):
            await fund.unapprove(document["id"])
        await settlement.delete([offset["id"], advance_ap["id"], advance_ar["id"]])
        await sales_receipt_service.delete([sales_receipt["id"]])
        await purchase_payment_service.delete([purchase_payment["id"]])
        await fund.delete([item["id"] for item in general_documents])

        closed = await period_service.close(period["id"])
        assert closed["status"] == "closed"
        try:
            await period_service.ensure_open(business_date, "跨期修改")
            raise AssertionError("已结账期间不应允许修改")
        except CustomException:
            pass
        reopened = await period_service.reopen(period["id"])
        assert reopened["status"] == "open"
        print("finance smoke: receipt/payment/transfer -> five writeoffs -> reversal -> close/reopen -> profit OK")
        await session.rollback()
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
