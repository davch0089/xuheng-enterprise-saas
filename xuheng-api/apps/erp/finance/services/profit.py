"""经营利润汇总和 SKU 维度毛利查询。"""

from datetime import date
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select

from apps.erp.master import models as master_models
from apps.erp.sales import models as sales_models
from .. import models


class ProfitQueryService:
    """按已审核销售、退货、成本和变动费用计算经营利润。"""

    def __init__(self, db):
        """绑定只读数据库会话。"""

        self.db = db

    async def report(self, date_start: date, date_end: date):
        """返回销售净收入、销售成本、毛利、贡献利润和退货冲回。"""

        delivery = await self.db.execute(select(
            func.coalesce(func.sum(sales_models.ErpSalesDelivery.total_amount), 0),
            func.coalesce(func.sum(sales_models.ErpSalesDelivery.total_cost), 0),
        ).where(
            sales_models.ErpSalesDelivery.status == "approved",
            sales_models.ErpSalesDelivery.business_date >= date_start,
            sales_models.ErpSalesDelivery.business_date <= date_end,
            sales_models.ErpSalesDelivery.is_delete == False,
        ))
        gross_sales, gross_cost = delivery.one()
        returns = await self.db.execute(select(
            func.coalesce(func.sum(sales_models.ErpSalesReturn.total_amount), 0),
            func.coalesce(func.sum(sales_models.ErpSalesReturn.total_cost), 0),
        ).where(
            sales_models.ErpSalesReturn.status == "approved",
            sales_models.ErpSalesReturn.business_date >= date_start,
            sales_models.ErpSalesReturn.business_date <= date_end,
            sales_models.ErpSalesReturn.is_delete == False,
        ))
        return_revenue, return_cost = returns.one()
        variable_expense = await self.db.scalar(select(func.coalesce(func.sum(models.ErpFundDocument.amount), 0)).where(
            models.ErpFundDocument.status == "approved",
            models.ErpFundDocument.document_type == "payment",
            models.ErpFundDocument.profit_category == "variable_expense",
            models.ErpFundDocument.business_date >= date_start,
            models.ErpFundDocument.business_date <= date_end,
            models.ErpFundDocument.is_delete == False,
        ))
        gross_sales, gross_cost = Decimal(gross_sales), Decimal(gross_cost)
        return_revenue, return_cost = Decimal(return_revenue), Decimal(return_cost)
        net_revenue = gross_sales - return_revenue
        sales_cost = gross_cost - return_cost
        gross_profit = net_revenue - sales_cost
        contribution_profit = gross_profit - Decimal(variable_expense)
        details = await self._details(date_start, date_end)
        return jsonable_encoder({
            "date_start": date_start, "date_end": date_end,
            "gross_sales": gross_sales,
            "sales_return_reversal": return_revenue,
            "net_sales_revenue": net_revenue,
            "gross_sales_cost": gross_cost,
            "return_cost_reversal": return_cost,
            "sales_cost": sales_cost,
            "gross_profit": gross_profit,
            "variable_expense": variable_expense,
            "contribution_profit": contribution_profit,
            "gross_margin_rate": gross_profit / net_revenue * 100 if net_revenue else 0,
            "details": details,
        })

    async def _details(self, date_start, date_end):
        """按 SKU 汇总销售收入、退货、成本及毛利。"""

        result = {}
        delivery_rows = (await self.db.execute(select(
            sales_models.ErpSalesDeliveryLine.product_id,
            func.sum(sales_models.ErpSalesDeliveryLine.amount),
            func.sum(sales_models.ErpSalesDeliveryLine.cost_amount),
        ).join(sales_models.ErpSalesDelivery, sales_models.ErpSalesDelivery.id == sales_models.ErpSalesDeliveryLine.delivery_id).where(
            sales_models.ErpSalesDelivery.status == "approved",
            sales_models.ErpSalesDelivery.business_date >= date_start,
            sales_models.ErpSalesDelivery.business_date <= date_end,
        ).group_by(sales_models.ErpSalesDeliveryLine.product_id))).all()
        return_rows = (await self.db.execute(select(
            sales_models.ErpSalesReturnLine.product_id,
            func.sum(sales_models.ErpSalesReturnLine.amount),
            func.sum(sales_models.ErpSalesReturnLine.cost_amount),
        ).join(sales_models.ErpSalesReturn, sales_models.ErpSalesReturn.id == sales_models.ErpSalesReturnLine.return_id).where(
            sales_models.ErpSalesReturn.status == "approved",
            sales_models.ErpSalesReturn.business_date >= date_start,
            sales_models.ErpSalesReturn.business_date <= date_end,
        ).group_by(sales_models.ErpSalesReturnLine.product_id))).all()
        product_ids = {row[0] for row in delivery_rows} | {row[0] for row in return_rows}
        products = {item.id: item for item in (await self.db.scalars(select(master_models.ErpProduct).where(master_models.ErpProduct.id.in_(product_ids or {0})))).all()}
        for product_id in product_ids:
            product = products.get(product_id)
            result[product_id] = {
                "product_id": product_id,
                "product_code": product.code if product else None,
                "product_name": product.name if product else None,
                "barcode": product.barcode if product else None,
                "variant_name": product.variant_name if product else None,
                "specification": product.specification if product else None,
                "gross_sales": Decimal(0), "sales_returns": Decimal(0),
                "gross_cost": Decimal(0), "return_cost": Decimal(0),
            }
        for product_id, revenue, cost in delivery_rows:
            result[product_id].update(gross_sales=Decimal(revenue or 0), gross_cost=Decimal(cost or 0))
        for product_id, revenue, cost in return_rows:
            result[product_id].update(sales_returns=Decimal(revenue or 0), return_cost=Decimal(cost or 0))
        rows = []
        for item in result.values():
            item["net_sales_revenue"] = item["gross_sales"] - item["sales_returns"]
            item["sales_cost"] = item["gross_cost"] - item["return_cost"]
            item["gross_profit"] = item["net_sales_revenue"] - item["sales_cost"]
            rows.append(item)
        return sorted(rows, key=lambda item: item["gross_profit"], reverse=True)
