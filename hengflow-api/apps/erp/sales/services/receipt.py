"""客户收款单保存、审核和核销服务。"""

from datetime import datetime
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, false, select
from sqlalchemy.dialects import mysql

from apps.erp.common import MONEY, quantize
from apps.erp.master import models as master_models
from core.exception import CustomException

from .. import models, schemas
from .common import SalesServiceSupport
from .receivable import ReceivableService


class SalesReceiptService(SalesServiceSupport):
    """负责客户收款草稿、审核、自动核销和反审核。"""

    def __init__(self, db, user_id: int | None = None):
        """绑定当前事务和操作人。"""

        self.db = db
        self.user_id = user_id
        self.receivables = ReceivableService(db, user_id)

    async def save(self, data: schemas.SalesReceiptInput, receipt_id: int | None = None):
        """新增或修改草稿收款单及预设核销明细。"""

        from apps.erp.finance.services.period import AccountingPeriodService
        await AccountingPeriodService(self.db, self.user_id).ensure_open(data.receipt_date, "新增或修改收款单")
        await self.active(master_models.ErpCustomer, data.customer_id, "客户")
        if data.settlement_method_id:
            await self.active(
                master_models.ErpSettlementMethod,
                data.settlement_method_id,
                "结算方式",
            )
        if sum((Decimal(x.amount) for x in data.allocations), Decimal(0)) > Decimal(data.amount):
            raise CustomException("核销金额不能大于收款金额")
        if receipt_id:
            receipt = await self._lock(receipt_id)
            if receipt.status != "draft":
                raise CustomException("只有草稿收款单可以修改")
            await self.db.execute(
                delete(models.ErpSalesReceiptAllocation).where(
                    models.ErpSalesReceiptAllocation.receipt_id == receipt_id
                )
            )
        else:
            number = data.receipt_no or await self.next_document_no(
                "sales_receipt", "RC", data.receipt_date
            )
            if await self.db.scalar(
                select(models.ErpSalesReceipt.id).where(
                    models.ErpSalesReceipt.receipt_no == number
                )
            ):
                raise CustomException("销售收款单号已存在")
            receipt = models.ErpSalesReceipt(receipt_no=number, created_by_id=self.user_id)
            self.db.add(receipt)
        receipt.receipt_date = data.receipt_date
        receipt.customer_id = data.customer_id
        receipt.settlement_method_id = data.settlement_method_id
        receipt.fund_account_id = data.fund_account_id
        receipt.amount = quantize(Decimal(data.amount), MONEY)
        receipt.remark = data.remark
        await self.db.flush()
        for allocation in data.allocations:
            self.db.add(
                models.ErpSalesReceiptAllocation(
                    receipt_id=receipt.id,
                    receivable_id=allocation.receivable_id,
                    amount=quantize(Decimal(allocation.amount), MONEY),
                )
            )
        await self.db.flush()
        return await self.detail(receipt.id)

    async def approve(self, receipt_id: int):
        """审核收款单并核销客户应收。"""

        receipt = await self._lock(receipt_id)
        if receipt.status != "draft":
            raise CustomException("只有草稿收款单可以审核")
        if not receipt.fund_account_id:
            raise CustomException("审核收款单前必须选择收款资金账户")
        allocations = list(
            (
                await self.db.scalars(
                    select(models.ErpSalesReceiptAllocation).where(
                        models.ErpSalesReceiptAllocation.receipt_id == receipt.id
                    )
                )
            ).all()
        )
        requested = [
            schemas.ReceiptAllocationInput(
                receivable_id=item.receivable_id, amount=item.amount
            )
            for item in allocations
        ]
        if allocations:
            await self.db.execute(
                delete(models.ErpSalesReceiptAllocation).where(
                    models.ErpSalesReceiptAllocation.receipt_id == receipt.id
                )
            )
            await self.db.flush()
        receipt.posting_version += 1
        receipt.status = "approved"
        receipt.approved_by_id = self.user_id
        receipt.approved_at = datetime.now()
        await self.db.flush()
        await self.receivables.approve_receipt(receipt, requested)
        from apps.erp.finance.services.fund import FundPostingEngine
        await FundPostingEngine(self.db, self.user_id).post(
            account_id=receipt.fund_account_id, amount=Decimal(receipt.amount),
            source_type="sales_receipt", source_id=receipt.id, source_no=receipt.receipt_no,
            posting_version=receipt.posting_version, entry_type="CUSTOMER_RECEIPT",
            occurred_at=datetime.combine(receipt.receipt_date, receipt.approved_at.time()),
        )
        return await self.detail(receipt.id)

    async def unapprove(self, receipt_id: int):
        """反审核收款单并撤销全部应收核销。"""

        receipt = await self._lock(receipt_id)
        if receipt.status != "approved":
            raise CustomException("只有已审核收款单可以反审核")
        from apps.erp.finance import models as finance_models
        linked = await self.db.scalar(select(finance_models.ErpSettlementDocument.id).where(
            finance_models.ErpSettlementDocument.source_receipt_id == receipt.id,
            finance_models.ErpSettlementDocument.status == "approved",
            finance_models.ErpSettlementDocument.is_delete == false(),
        ).limit(1))
        if linked is not None:
            raise CustomException("收款已被预收核销单使用，请先反审核核销单")
        from apps.erp.finance.services.fund import FundPostingEngine
        await FundPostingEngine(self.db, self.user_id).reverse("sales_receipt", receipt.id, receipt.posting_version)
        await self.receivables.unapprove_receipt(receipt)
        receipt.status = "draft"
        receipt.approved_by_id = None
        receipt.approved_at = None
        await self.db.flush()
        return await self.detail(receipt.id)

    async def delete(self, ids: list[int]):
        """批量删除草稿收款单。"""

        docs = list(
            (
                await self.db.scalars(
                    select(models.ErpSalesReceipt).where(
                        models.ErpSalesReceipt.id.in_(ids),
                        models.ErpSalesReceipt.is_delete == false(),
                    )
                )
            ).all()
        )
        if len(docs) != len(set(ids)) or any(item.status != "draft" for item in docs):
            raise CustomException("只能删除存在的草稿收款单")
        from apps.erp.finance.services.period import AccountingPeriodService
        for item in docs:
            await AccountingPeriodService(self.db, self.user_id).ensure_open(item.receipt_date, "删除收款单")
        await self.db.execute(
            delete(models.ErpSalesReceiptAllocation).where(
                models.ErpSalesReceiptAllocation.receipt_id.in_(ids)
            )
        )
        for item in docs:
            item.is_delete = True
        await self.db.flush()

    async def detail(self, receipt_id: int):
        """返回收款单和核销明细。"""

        receipt = await self.db.get(models.ErpSalesReceipt, receipt_id)
        if receipt is None or receipt.is_delete:
            raise CustomException("销售收款单不存在")
        await self.db.refresh(receipt)
        result = {key: getattr(receipt, key) for key in receipt.get_column_attrs()}
        allocations = list(
            (
                await self.db.execute(
                    select(models.ErpSalesReceiptAllocation, models.ErpReceivable)
                    .join(
                        models.ErpReceivable,
                        models.ErpReceivable.id
                        == models.ErpSalesReceiptAllocation.receivable_id,
                    )
                    .where(models.ErpSalesReceiptAllocation.receipt_id == receipt_id)
                    .order_by(models.ErpSalesReceiptAllocation.id)
                )
            ).all()
        )
        result["allocations"] = [
            {
                **{key: getattr(allocation, key) for key in allocation.get_column_attrs()},
                "receivable_no": receivable.receivable_no,
                "delivery_no": receivable.delivery_no,
                "outstanding_amount": receivable.outstanding_amount,
                "receivable_status": receivable.status,
            }
            for allocation, receivable in allocations
        ]
        return jsonable_encoder(result)

    async def _lock(self, receipt_id: int):
        """锁定销售收款单。"""

        receipt = await self.db.scalar(
            select(models.ErpSalesReceipt)
            .where(
                models.ErpSalesReceipt.id == receipt_id,
                models.ErpSalesReceipt.is_delete == false(),
            )
            .with_for_update()
        )
        if receipt is None:
            raise CustomException("销售收款单不存在")
        return receipt
