"""ERP 经营驾驶舱聚合查询服务。"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import false, func, select

from apps.erp.finance import models as finance_models
from apps.erp.finance.services.profit import ProfitQueryService
from apps.erp.inventory import models as inventory_models
from apps.erp.master import models as master_models
from apps.erp.purchase import models as purchase_models
from apps.erp.sales import models as sales_models


ZERO = Decimal("0")


class ErpDashboardService:
    """从现有 ERP 业务表生成只读经营驾驶舱数据。"""

    def __init__(self, db):
        """绑定只读数据库会话。"""

        self.db = db

    async def overview(self, days: int = 30):
        """聚合经营指标、趋势、排行、库存结构、预警和近期单据。"""

        date_end = date.today()
        date_start = date_end - timedelta(days=days - 1)
        profit = await ProfitQueryService(self.db).report(date_start, date_end)
        balances = await self._balances(date_end)
        purchase_amount = await self._purchase_amount(date_start, date_end)
        trend = await self._trend(date_start, date_end)
        warehouses = await self._warehouse_inventory()
        risks = await self._risks(date_end)
        recent_documents = await self._recent_documents()
        top_products = sorted(
            profit.get("details", []),
            key=lambda item: Decimal(str(item.get("net_sales_revenue") or 0)),
            reverse=True,
        )[:8]
        summary = {
            "net_sales_revenue": profit["net_sales_revenue"],
            "sales_cost": profit["sales_cost"],
            "gross_profit": profit["gross_profit"],
            "gross_margin_rate": profit["gross_margin_rate"],
            "purchase_amount": purchase_amount,
            **balances,
        }
        return jsonable_encoder(
            {
                "generated_at": datetime.now(),
                "date_start": date_start,
                "date_end": date_end,
                "days": days,
                "summary": summary,
                "trend": trend,
                "top_products": top_products,
                "warehouse_inventory": warehouses,
                "risks": risks,
                "recent_documents": recent_documents,
            }
        )

    async def _balances(self, today: date):
        """汇总库存、资金、应收应付及逾期余额。"""

        cost = inventory_models.ErpInventoryCostBalance
        inventory_quantity, inventory_value = (
            await self.db.execute(
                select(
                    func.coalesce(func.sum(cost.quantity), 0),
                    func.coalesce(func.sum(cost.inventory_value), 0),
                ).where(cost.is_delete == false())
            )
        ).one()
        account = finance_models.ErpFundAccount
        account_balance = finance_models.ErpFundAccountBalance
        fund_balance = await self.db.scalar(
            select(func.coalesce(func.sum(account_balance.amount), 0))
            .join(account, account.id == account_balance.account_id)
            .where(
                account.is_delete == false(),
                account_balance.is_delete == false(),
                account.is_active == True,
            )
        )
        receivable = sales_models.ErpReceivable
        receivable_outstanding, overdue_receivable = (
            await self.db.execute(
                select(
                    func.coalesce(func.sum(receivable.outstanding_amount), 0),
                    func.coalesce(
                        func.sum(
                            func.if_(
                                receivable.due_date < today,
                                receivable.outstanding_amount,
                                0,
                            )
                        ),
                        0,
                    ),
                ).where(
                    receivable.is_delete == false(),
                    receivable.outstanding_amount > 0,
                )
            )
        ).one()
        payable = purchase_models.ErpPayable
        payable_outstanding, overdue_payable = (
            await self.db.execute(
                select(
                    func.coalesce(func.sum(payable.outstanding_amount), 0),
                    func.coalesce(
                        func.sum(
                            func.if_(payable.due_date < today, payable.outstanding_amount, 0)
                        ),
                        0,
                    ),
                ).where(
                    payable.is_delete == false(),
                    payable.outstanding_amount > 0,
                )
            )
        ).one()
        return {
            "inventory_quantity": inventory_quantity,
            "inventory_value": inventory_value,
            "fund_balance": fund_balance or ZERO,
            "receivable_outstanding": receivable_outstanding,
            "payable_outstanding": payable_outstanding,
            "overdue_receivable": overdue_receivable,
            "overdue_payable": overdue_payable,
        }

    async def _purchase_amount(self, date_start: date, date_end: date):
        """计算周期内采购收货减采购退货后的价税合计。"""

        receipts = await self.db.scalar(
            select(func.coalesce(func.sum(purchase_models.ErpPurchaseReceipt.payable_amount), 0)).where(
                purchase_models.ErpPurchaseReceipt.status == "approved",
                purchase_models.ErpPurchaseReceipt.business_date.between(date_start, date_end),
                purchase_models.ErpPurchaseReceipt.is_delete == false(),
            )
        )
        returns = await self.db.scalar(
            select(func.coalesce(func.sum(purchase_models.ErpPurchaseReturn.payable_amount), 0)).where(
                purchase_models.ErpPurchaseReturn.status == "approved",
                purchase_models.ErpPurchaseReturn.business_date.between(date_start, date_end),
                purchase_models.ErpPurchaseReturn.is_delete == false(),
            )
        )
        return Decimal(receipts or 0) - Decimal(returns or 0)

    async def _trend(self, date_start: date, date_end: date):
        """按日生成销售净收入、毛利和采购净额趋势，空白日期补零。"""

        result = {}
        current = date_start
        while current <= date_end:
            result[current] = {
                "date": current,
                "sales_revenue": ZERO,
                "gross_profit": ZERO,
                "purchase_amount": ZERO,
            }
            current += timedelta(days=1)

        delivery_rows = (
            await self.db.execute(
                select(
                    sales_models.ErpSalesDelivery.business_date,
                    func.sum(sales_models.ErpSalesDelivery.total_amount),
                    func.sum(sales_models.ErpSalesDelivery.gross_profit),
                )
                .where(
                    sales_models.ErpSalesDelivery.status == "approved",
                    sales_models.ErpSalesDelivery.business_date.between(date_start, date_end),
                    sales_models.ErpSalesDelivery.is_delete == false(),
                )
                .group_by(sales_models.ErpSalesDelivery.business_date)
            )
        ).all()
        return_rows = (
            await self.db.execute(
                select(
                    sales_models.ErpSalesReturn.business_date,
                    func.sum(sales_models.ErpSalesReturn.total_amount),
                    func.sum(
                        sales_models.ErpSalesReturn.total_amount
                        - sales_models.ErpSalesReturn.total_cost
                    ),
                )
                .where(
                    sales_models.ErpSalesReturn.status == "approved",
                    sales_models.ErpSalesReturn.business_date.between(date_start, date_end),
                    sales_models.ErpSalesReturn.is_delete == false(),
                )
                .group_by(sales_models.ErpSalesReturn.business_date)
            )
        ).all()
        purchase_receipts = (
            await self.db.execute(
                select(
                    purchase_models.ErpPurchaseReceipt.business_date,
                    func.sum(purchase_models.ErpPurchaseReceipt.payable_amount),
                )
                .where(
                    purchase_models.ErpPurchaseReceipt.status == "approved",
                    purchase_models.ErpPurchaseReceipt.business_date.between(date_start, date_end),
                    purchase_models.ErpPurchaseReceipt.is_delete == false(),
                )
                .group_by(purchase_models.ErpPurchaseReceipt.business_date)
            )
        ).all()
        purchase_returns = (
            await self.db.execute(
                select(
                    purchase_models.ErpPurchaseReturn.business_date,
                    func.sum(purchase_models.ErpPurchaseReturn.payable_amount),
                )
                .where(
                    purchase_models.ErpPurchaseReturn.status == "approved",
                    purchase_models.ErpPurchaseReturn.business_date.between(date_start, date_end),
                    purchase_models.ErpPurchaseReturn.is_delete == false(),
                )
                .group_by(purchase_models.ErpPurchaseReturn.business_date)
            )
        ).all()
        for business_date, revenue, gross_profit in delivery_rows:
            result[business_date]["sales_revenue"] += Decimal(revenue or 0)
            result[business_date]["gross_profit"] += Decimal(gross_profit or 0)
        for business_date, revenue, gross_profit in return_rows:
            result[business_date]["sales_revenue"] -= Decimal(revenue or 0)
            result[business_date]["gross_profit"] -= Decimal(gross_profit or 0)
        for business_date, amount in purchase_receipts:
            result[business_date]["purchase_amount"] += Decimal(amount or 0)
        for business_date, amount in purchase_returns:
            result[business_date]["purchase_amount"] -= Decimal(amount or 0)
        return list(result.values())

    async def _warehouse_inventory(self):
        """按仓库汇总成本余额数量、库存金额和 SKU 数量。"""

        cost = inventory_models.ErpInventoryCostBalance
        warehouse = master_models.ErpWarehouse
        rows = (
            await self.db.execute(
                select(
                    warehouse.id,
                    warehouse.code,
                    warehouse.name,
                    func.coalesce(func.sum(cost.quantity), 0),
                    func.coalesce(func.sum(cost.inventory_value), 0),
                    func.count(cost.product_id),
                )
                .outerjoin(
                    cost,
                    (cost.warehouse_id == warehouse.id) & (cost.is_delete == false()),
                )
                .where(warehouse.is_delete == false(), warehouse.is_active == True)
                .group_by(warehouse.id, warehouse.code, warehouse.name)
                .order_by(func.coalesce(func.sum(cost.inventory_value), 0).desc())
            )
        ).all()
        return [
            {
                "warehouse_id": warehouse_id,
                "warehouse_code": code,
                "warehouse_name": name,
                "quantity": quantity,
                "inventory_value": inventory_value,
                "sku_count": sku_count,
            }
            for warehouse_id, code, name, quantity, inventory_value, sku_count in rows
        ]

    async def _risks(self, today: date):
        """生成低库存、近效期、逾期应收和逾期应付预警。"""

        low_stock = await self._low_stock_risks()
        expiring = await self._expiring_batch_risks(today)
        overdue_receivables = await self._overdue_receivable_risks(today)
        overdue_payables = await self._overdue_payable_risks(today)
        items = sorted(
            low_stock[:4] + expiring[:4] + overdue_receivables[:4] + overdue_payables[:4],
            key=lambda item: (item["level"] != "high", item.get("days") or 0),
        )[:12]
        return {
            "low_stock_count": len(low_stock),
            "expiring_batch_count": len(expiring),
            "overdue_receivable_count": len(overdue_receivables),
            "overdue_payable_count": len(overdue_payables),
            "items": items,
        }

    async def _low_stock_risks(self):
        """返回库存总量低于 SKU 最低库存的商品。"""

        product = master_models.ErpProduct
        balance = inventory_models.ErpInventoryBalance
        quantity = func.coalesce(func.sum(balance.quantity), 0)
        rows = (
            await self.db.execute(
                select(product, quantity)
                .outerjoin(
                    balance,
                    (balance.product_id == product.id) & (balance.is_delete == false()),
                )
                .where(
                    product.is_delete == false(),
                    product.is_active == True,
                    product.min_stock > 0,
                )
                .group_by(product.id)
                .having(quantity < product.min_stock)
                .order_by((product.min_stock - quantity).desc())
            )
        ).all()
        return [
            {
                "type": "low_stock",
                "level": "high" if Decimal(qty) <= 0 else "medium",
                "title": f"{item.code} {item.name}",
                "description": f"现存 {qty}，最低库存 {item.min_stock}",
                "quantity": qty,
            }
            for item, qty in rows
        ]

    async def _expiring_batch_risks(self, today: date):
        """返回未来 30 天内到期且仍有可用库存的批次。"""

        batch = inventory_models.ErpInventoryBatchBalance
        product = master_models.ErpProduct
        warehouse = master_models.ErpWarehouse
        rows = (
            await self.db.execute(
                select(batch, product.code, product.name, warehouse.name)
                .join(product, product.id == batch.product_id)
                .join(warehouse, warehouse.id == batch.warehouse_id)
                .where(
                    batch.is_delete == false(),
                    batch.expiry_date.is_not(None),
                    batch.expiry_date.between(today, today + timedelta(days=30)),
                    batch.quantity > batch.reserved_quantity + batch.frozen_quantity,
                )
                .order_by(batch.expiry_date, batch.id)
            )
        ).all()
        return [
            {
                "type": "expiring_batch",
                "level": "high" if (item.expiry_date - today).days <= 7 else "medium",
                "title": f"{code} 批次 {item.batch_no}",
                "description": f"{warehouse_name} / {name} / {item.expiry_date} 到期",
                "quantity": Decimal(item.quantity)
                - Decimal(item.reserved_quantity)
                - Decimal(item.frozen_quantity),
                "days": (item.expiry_date - today).days,
            }
            for item, code, name, warehouse_name in rows
        ]

    async def _overdue_receivable_risks(self, today: date):
        """返回按金额排序的逾期客户应收。"""

        receivable = sales_models.ErpReceivable
        customer = master_models.ErpCustomer
        rows = (
            await self.db.execute(
                select(receivable, customer.name)
                .join(customer, customer.id == receivable.customer_id)
                .where(
                    receivable.is_delete == false(),
                    receivable.outstanding_amount > 0,
                    receivable.due_date < today,
                )
                .order_by(receivable.outstanding_amount.desc())
            )
        ).all()
        return [
            {
                "type": "overdue_receivable",
                "level": "high",
                "title": f"客户应收逾期 · {customer_name}",
                "description": f"{item.receivable_no}，逾期 {(today - item.due_date).days} 天",
                "amount": item.outstanding_amount,
                "days": (today - item.due_date).days,
            }
            for item, customer_name in rows
        ]

    async def _overdue_payable_risks(self, today: date):
        """返回按金额排序的逾期供应商应付。"""

        payable = purchase_models.ErpPayable
        supplier = master_models.ErpSupplier
        rows = (
            await self.db.execute(
                select(payable, supplier.name)
                .join(supplier, supplier.id == payable.supplier_id)
                .where(
                    payable.is_delete == false(),
                    payable.outstanding_amount > 0,
                    payable.due_date < today,
                )
                .order_by(payable.outstanding_amount.desc())
            )
        ).all()
        return [
            {
                "type": "overdue_payable",
                "level": "high",
                "title": f"供应商应付逾期 · {supplier_name}",
                "description": f"{item.payable_no}，逾期 {(today - item.due_date).days} 天",
                "amount": item.outstanding_amount,
                "days": (today - item.due_date).days,
            }
            for item, supplier_name in rows
        ]

    async def _recent_documents(self):
        """合并最近审核的销售、采购和资金单据。"""

        deliveries = (
            await self.db.execute(
                select(sales_models.ErpSalesDelivery, master_models.ErpCustomer.name)
                .join(
                    master_models.ErpCustomer,
                    master_models.ErpCustomer.id == sales_models.ErpSalesDelivery.customer_id,
                )
                .where(
                    sales_models.ErpSalesDelivery.status == "approved",
                    sales_models.ErpSalesDelivery.is_delete == false(),
                )
                .order_by(sales_models.ErpSalesDelivery.approved_at.desc())
                .limit(6)
            )
        ).all()
        receipts = (
            await self.db.execute(
                select(purchase_models.ErpPurchaseReceipt, master_models.ErpSupplier.name)
                .join(
                    master_models.ErpSupplier,
                    master_models.ErpSupplier.id == purchase_models.ErpPurchaseReceipt.supplier_id,
                )
                .where(
                    purchase_models.ErpPurchaseReceipt.status == "approved",
                    purchase_models.ErpPurchaseReceipt.is_delete == false(),
                )
                .order_by(purchase_models.ErpPurchaseReceipt.approved_at.desc())
                .limit(6)
            )
        ).all()
        funds = list(
            (
                await self.db.scalars(
                    select(finance_models.ErpFundDocument)
                    .where(
                        finance_models.ErpFundDocument.status == "approved",
                        finance_models.ErpFundDocument.is_delete == false(),
                    )
                    .order_by(finance_models.ErpFundDocument.approved_at.desc())
                    .limit(6)
                )
            ).all()
        )
        result = [
            {
                "type": "sales_delivery",
                "type_label": "销售出库",
                "document_no": item.delivery_no,
                "business_date": item.business_date,
                "partner": partner,
                "amount": item.payable_amount,
                "occurred_at": item.approved_at,
            }
            for item, partner in deliveries
        ]
        result.extend(
            {
                "type": "purchase_receipt",
                "type_label": "采购入库",
                "document_no": item.receipt_no,
                "business_date": item.business_date,
                "partner": partner,
                "amount": item.payable_amount,
                "occurred_at": item.approved_at,
            }
            for item, partner in receipts
        )
        fund_labels = {"receipt": "其他收款", "payment": "其他付款", "transfer": "账户转账"}
        result.extend(
            {
                "type": f"fund_{item.document_type}",
                "type_label": fund_labels.get(item.document_type, "资金单据"),
                "document_no": item.document_no,
                "business_date": item.business_date,
                "partner": item.counterparty or "内部账户",
                "amount": item.amount,
                "occurred_at": item.approved_at,
            }
            for item in funds
        )
        return sorted(
            result,
            key=lambda item: item["occurred_at"] or datetime.min,
            reverse=True,
        )[:12]
