"""财务表单选项和开放项目只读查询。"""

from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import false, func, select

from apps.erp.master import models as master
from apps.erp.purchase import models as purchase
from apps.erp.sales import models as sales
from .services.fund import FundDocumentService


class FinanceQueryService:
    """提供资金、核销页面使用的基础资料和开放项目。"""

    def __init__(self, db):
        """绑定只读数据库会话。"""

        self.db = db

    async def options(self):
        """返回资金账户、客户和供应商选项。"""

        async def partner_options(model):
            """把启用往来单位转换成下拉选项。"""

            rows = list((await self.db.scalars(select(model).where(model.is_delete == false(), model.is_active == True).order_by(model.code))).all())
            return [{"value": item.id, "label": f"{item.code} - {item.name}"} for item in rows]
        return jsonable_encoder({
            "accounts": await FundDocumentService(self.db).options(),
            "customers": await partner_options(master.ErpCustomer),
            "suppliers": await partner_options(master.ErpSupplier),
        })

    async def open_items(self, customer_id=None, supplier_id=None):
        """返回可核销应收应付及可用预收预付来源。"""

        receivables, payables, receipts, payments = [], [], [], []
        if customer_id:
            receivables = list((await self.db.scalars(select(sales.ErpReceivable).where(
                sales.ErpReceivable.customer_id == customer_id,
                sales.ErpReceivable.outstanding_amount > 0,
                sales.ErpReceivable.is_delete == false(),
            ).order_by(sales.ErpReceivable.due_date, sales.ErpReceivable.id))).all())
            receipt_rows = (await self.db.execute(select(
                sales.ErpSalesReceipt,
                func.coalesce(func.sum(sales.ErpSalesReceiptAllocation.amount), 0),
            ).outerjoin(sales.ErpSalesReceiptAllocation, sales.ErpSalesReceiptAllocation.receipt_id == sales.ErpSalesReceipt.id).where(
                sales.ErpSalesReceipt.customer_id == customer_id,
                sales.ErpSalesReceipt.status == "approved",
                sales.ErpSalesReceipt.is_delete == false(),
            ).group_by(sales.ErpSalesReceipt.id))).all()
            receipts = [{**self._columns(item), "unused_amount": Decimal(item.amount) - Decimal(used)} for item, used in receipt_rows if Decimal(item.amount) > Decimal(used)]
        if supplier_id:
            payables = list((await self.db.scalars(select(purchase.ErpPayable).where(
                purchase.ErpPayable.supplier_id == supplier_id,
                purchase.ErpPayable.outstanding_amount > 0,
                purchase.ErpPayable.is_delete == false(),
            ).order_by(purchase.ErpPayable.due_date, purchase.ErpPayable.id))).all())
            payment_rows = (await self.db.execute(select(
                purchase.ErpPurchasePayment,
                func.coalesce(func.sum(purchase.ErpPurchasePaymentAllocation.amount), 0),
            ).outerjoin(purchase.ErpPurchasePaymentAllocation, purchase.ErpPurchasePaymentAllocation.payment_id == purchase.ErpPurchasePayment.id).where(
                purchase.ErpPurchasePayment.supplier_id == supplier_id,
                purchase.ErpPurchasePayment.status == "approved",
                purchase.ErpPurchasePayment.is_delete == false(),
            ).group_by(purchase.ErpPurchasePayment.id))).all()
            payments = [{**self._columns(item), "unused_amount": Decimal(item.amount) - Decimal(used)} for item, used in payment_rows if Decimal(item.amount) > Decimal(used)]
        return jsonable_encoder({
            "receivables": [self._columns(item) for item in receivables],
            "payables": [self._columns(item) for item in payables],
            "receipts": receipts,
            "payments": payments,
        })

    @staticmethod
    def _columns(obj):
        """序列化 ORM 实体。"""

        return {key: getattr(obj, key) for key in obj.get_column_attrs()}
