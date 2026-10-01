"""五类核销中的预收、预付和应收应付对冲服务。"""

from datetime import datetime
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, false, func, select

from apps.erp.common import MONEY, quantize
from apps.erp.purchase import models as purchase_models
from apps.erp.purchase.services.payable import PayableService
from apps.erp.sales import models as sales_models
from apps.erp.sales.services.receivable import ReceivableService
from core.exception import CustomException
from .. import models, schemas
from .common import columns, next_no
from .period import AccountingPeriodService


class SettlementService:
    """处理预收冲应收、预付冲应付及应收应付对冲。"""

    TYPES = {"advance_receipt_ar", "advance_payment_ap", "ar_ap_offset"}

    def __init__(self, db, user_id: int | None = None):
        """绑定当前事务和操作人。"""

        self.db = db
        self.user_id = user_id

    async def save(self, data: schemas.SettlementDocumentInput, document_id: int | None = None):
        """新增或修改财务核销草稿并校验两侧金额。"""

        await AccountingPeriodService(self.db, self.user_id).ensure_open(data.business_date, "新增或修改核销单")
        if data.writeoff_type not in self.TYPES:
            raise CustomException("不支持的核销类型")
        self._validate_input(data)
        if document_id:
            document = await self._lock(document_id)
            if document.status != "draft":
                raise CustomException("只有草稿核销单可以修改")
            await self.db.execute(delete(models.ErpSettlementAllocation).where(models.ErpSettlementAllocation.document_id == document.id))
        else:
            number = data.document_no or await next_no(self.db, "finance_settlement", "WO", data.business_date)
            document = models.ErpSettlementDocument(document_no=number, created_by_id=self.user_id)
            self.db.add(document)
        for field in ("writeoff_type", "business_date", "customer_id", "supplier_id", "source_receipt_id", "source_payment_id", "amount", "remark"):
            setattr(document, field, getattr(data, field))
        await self.db.flush()
        for item in data.allocations:
            self.db.add(models.ErpSettlementAllocation(document_id=document.id, **item.model_dump()))
        await self.db.flush()
        return await self.detail(document.id)

    async def approve(self, document_id: int):
        """审核核销单并锁定、更新对应开放项目。"""

        document = await self._lock(document_id)
        if document.status != "draft":
            raise CustomException("只有草稿核销单可以审核")
        await AccountingPeriodService(self.db, self.user_id).ensure_open(document.business_date, "审核核销单")
        allocations = await self._allocations(document.id, True)
        version, now = document.posting_version + 1, datetime.now()
        if document.writeoff_type == "advance_receipt_ar":
            await self._apply_advance_receipt(document, allocations, Decimal(1))
        elif document.writeoff_type == "advance_payment_ap":
            await self._apply_advance_payment(document, allocations, Decimal(1))
        else:
            await self._apply_offset(document, allocations, Decimal(1), version, now)
        document.status, document.posting_version = "approved", version
        document.approved_by_id, document.approved_at = self.user_id, now
        await self.db.flush()
        return await self.detail(document.id)

    async def unapprove(self, document_id: int):
        """反审核核销单并恢复开放项目或生成反向应收应付流水。"""

        document = await self._lock(document_id)
        if document.status != "approved":
            raise CustomException("只有已审核核销单可以反审核")
        await AccountingPeriodService(self.db, self.user_id).ensure_open(document.business_date, "反审核核销单")
        allocations = await self._allocations(document.id, True)
        if document.writeoff_type == "advance_receipt_ar":
            await self._apply_advance_receipt(document, allocations, Decimal(-1))
        elif document.writeoff_type == "advance_payment_ap":
            await self._apply_advance_payment(document, allocations, Decimal(-1))
        else:
            await self._apply_offset(document, allocations, Decimal(-1), document.posting_version, datetime.now())
        document.status, document.approved_by_id, document.approved_at = "draft", None, None
        await self.db.flush()
        return await self.detail(document.id)

    async def _apply_advance_receipt(self, document, allocations, direction):
        """将已审核收款的未核销预收金额分配到应收开放项目。"""

        receipt = await self.db.scalar(select(sales_models.ErpSalesReceipt).where(
            sales_models.ErpSalesReceipt.id == document.source_receipt_id,
            sales_models.ErpSalesReceipt.status == "approved",
            sales_models.ErpSalesReceipt.customer_id == document.customer_id,
        ).with_for_update())
        if receipt is None:
            raise CustomException("预收来源收款不存在、未审核或客户不一致")
        used = await self.db.scalar(select(func.coalesce(func.sum(sales_models.ErpSalesReceiptAllocation.amount), 0)).where(
            sales_models.ErpSalesReceiptAllocation.receipt_id == receipt.id
        ))
        if direction > 0 and Decimal(used) + Decimal(document.amount) > Decimal(receipt.amount):
            raise CustomException("预收可核销余额不足")
        for item in allocations:
            if item.target_type != "receivable":
                raise CustomException("预收只能核销应收项目")
            receivable = await self._receivable(item.target_id, document.customer_id)
            amount = Decimal(item.amount)
            if direction > 0 and amount > Decimal(receivable.outstanding_amount):
                raise CustomException("核销金额超过应收未收金额")
            receivable.settled_amount = quantize(Decimal(receivable.settled_amount) + direction * amount, MONEY)
            receivable.outstanding_amount = quantize(Decimal(receivable.outstanding_amount) - direction * amount, MONEY)
            ReceivableService._refresh_status(receivable)
            existing = await self.db.scalar(select(sales_models.ErpSalesReceiptAllocation).where(
                sales_models.ErpSalesReceiptAllocation.receipt_id == receipt.id,
                sales_models.ErpSalesReceiptAllocation.receivable_id == receivable.id,
            ).with_for_update())
            if existing:
                existing.amount = quantize(Decimal(existing.amount) + direction * amount, MONEY)
                if existing.amount == 0:
                    await self.db.delete(existing)
            elif direction > 0:
                self.db.add(sales_models.ErpSalesReceiptAllocation(receipt_id=receipt.id, receivable_id=receivable.id, amount=amount))

    async def _apply_advance_payment(self, document, allocations, direction):
        """将已审核付款的未核销预付金额分配到应付开放项目。"""

        payment = await self.db.scalar(select(purchase_models.ErpPurchasePayment).where(
            purchase_models.ErpPurchasePayment.id == document.source_payment_id,
            purchase_models.ErpPurchasePayment.status == "approved",
            purchase_models.ErpPurchasePayment.supplier_id == document.supplier_id,
        ).with_for_update())
        if payment is None:
            raise CustomException("预付来源付款不存在、未审核或供应商不一致")
        used = await self.db.scalar(select(func.coalesce(func.sum(purchase_models.ErpPurchasePaymentAllocation.amount), 0)).where(
            purchase_models.ErpPurchasePaymentAllocation.payment_id == payment.id
        ))
        if direction > 0 and Decimal(used) + Decimal(document.amount) > Decimal(payment.amount):
            raise CustomException("预付可核销余额不足")
        for item in allocations:
            if item.target_type != "payable":
                raise CustomException("预付只能核销应付项目")
            payable = await self._payable(item.target_id, document.supplier_id)
            amount = Decimal(item.amount)
            if direction > 0 and amount > Decimal(payable.outstanding_amount):
                raise CustomException("核销金额超过应付未付金额")
            payable.settled_amount = quantize(Decimal(payable.settled_amount) + direction * amount, MONEY)
            payable.outstanding_amount = quantize(Decimal(payable.outstanding_amount) - direction * amount, MONEY)
            PayableService._refresh_status(payable)
            existing = await self.db.scalar(select(purchase_models.ErpPurchasePaymentAllocation).where(
                purchase_models.ErpPurchasePaymentAllocation.payment_id == payment.id,
                purchase_models.ErpPurchasePaymentAllocation.payable_id == payable.id,
            ).with_for_update())
            if existing:
                existing.amount = quantize(Decimal(existing.amount) + direction * amount, MONEY)
                if existing.amount == 0:
                    await self.db.delete(existing)
            elif direction > 0:
                self.db.add(purchase_models.ErpPurchasePaymentAllocation(payment_id=payment.id, payable_id=payable.id, amount=amount))

    async def _apply_offset(self, document, allocations, direction, version, now):
        """同步核销应收与应付；正向减少双方余额，反向生成双方冲销流水。"""

        for item in allocations:
            amount = Decimal(item.amount)
            if item.target_type == "receivable":
                target = await self._receivable(item.target_id, document.customer_id)
                if direction > 0 and amount > Decimal(target.outstanding_amount):
                    raise CustomException("对冲金额超过应收未收金额")
                target.settled_amount = quantize(Decimal(target.settled_amount) + direction * amount, MONEY)
                target.outstanding_amount = quantize(Decimal(target.outstanding_amount) - direction * amount, MONEY)
                ReceivableService._refresh_status(target)
            elif item.target_type == "payable":
                target = await self._payable(item.target_id, document.supplier_id)
                if direction > 0 and amount > Decimal(target.outstanding_amount):
                    raise CustomException("对冲金额超过应付未付金额")
                target.settled_amount = quantize(Decimal(target.settled_amount) + direction * amount, MONEY)
                target.outstanding_amount = quantize(Decimal(target.outstanding_amount) - direction * amount, MONEY)
                PayableService._refresh_status(target)
        if direction > 0:
            occurred = datetime.combine(document.business_date, now.time())
            await ReceivableService(self.db, self.user_id).post_entry(customer_id=document.customer_id, receivable_id=None, source_type="finance_settlement", source_id=document.id, source_no=document.document_no, posting_version=version, entry_type="AR_AP_OFFSET", amount=-Decimal(document.amount), occurred_at=occurred)
            await PayableService(self.db, self.user_id).post_entry(supplier_id=document.supplier_id, payable_id=None, source_type="finance_settlement", source_id=document.id, source_no=document.document_no, posting_version=version, entry_type="AR_AP_OFFSET", amount=-Decimal(document.amount), occurred_at=occurred)
        else:
            await ReceivableService(self.db, self.user_id).reverse_entry("finance_settlement", document.id, version)
            await PayableService(self.db, self.user_id).reverse_entry("finance_settlement", document.id, version)

    def _validate_input(self, data):
        """校验核销类型要求的来源、对象和两侧金额。"""

        ar = sum((Decimal(item.amount) for item in data.allocations if item.target_type == "receivable"), Decimal(0))
        ap = sum((Decimal(item.amount) for item in data.allocations if item.target_type == "payable"), Decimal(0))
        if data.writeoff_type == "advance_receipt_ar" and (not data.customer_id or not data.source_receipt_id or ar != data.amount or ap):
            raise CustomException("预收冲应收必须选择客户、来源收款且应收核销合计等于单据金额")
        if data.writeoff_type == "advance_payment_ap" and (not data.supplier_id or not data.source_payment_id or ap != data.amount or ar):
            raise CustomException("预付冲应付必须选择供应商、来源付款且应付核销合计等于单据金额")
        if data.writeoff_type == "ar_ap_offset" and (not data.customer_id or not data.supplier_id or ar != data.amount or ap != data.amount):
            raise CustomException("应收应付对冲必须选择客户和供应商，且双方核销合计都等于单据金额")

    async def list(self, page, limit, writeoff_type=None, status=None):
        """分页查询核销单。"""

        conditions = [models.ErpSettlementDocument.is_delete == false()]
        if writeoff_type:
            conditions.append(models.ErpSettlementDocument.writeoff_type == writeoff_type)
        if status:
            conditions.append(models.ErpSettlementDocument.status == status)
        count = await self.db.scalar(select(func.count(models.ErpSettlementDocument.id)).where(*conditions))
        rows = list((await self.db.scalars(select(models.ErpSettlementDocument).where(*conditions).order_by(models.ErpSettlementDocument.business_date.desc(), models.ErpSettlementDocument.id.desc()).offset((page - 1) * limit).limit(limit))).all())
        return jsonable_encoder([columns(item) for item in rows]), count or 0

    async def detail(self, document_id):
        """返回核销单及应收应付分配明细。"""

        document = await self.db.get(models.ErpSettlementDocument, document_id)
        if document is None or document.is_delete:
            raise CustomException("核销单不存在")
        allocations = await self._allocations(document_id)
        return jsonable_encoder({**columns(document), "allocations": [columns(item) for item in allocations]})

    async def delete(self, ids):
        """删除核销草稿。"""

        rows = list((await self.db.scalars(select(models.ErpSettlementDocument).where(models.ErpSettlementDocument.id.in_(ids), models.ErpSettlementDocument.is_delete == false()))).all())
        if len(rows) != len(set(ids)) or any(item.status != "draft" for item in rows):
            raise CustomException("只能删除存在的草稿核销单")
        for item in rows:
            await AccountingPeriodService(self.db, self.user_id).ensure_open(item.business_date, "删除核销单")
            item.is_delete = True
        await self.db.flush()

    async def _receivable(self, target_id, customer_id):
        """锁定客户应收开放项目。"""

        target = await self.db.scalar(select(sales_models.ErpReceivable).where(
            sales_models.ErpReceivable.id == target_id,
            sales_models.ErpReceivable.customer_id == customer_id,
        ).with_for_update())
        if target is None:
            raise CustomException("应收核销项目不存在或客户不一致")
        return target

    async def _payable(self, target_id, supplier_id):
        """锁定供应商应付开放项目。"""

        target = await self.db.scalar(select(purchase_models.ErpPayable).where(
            purchase_models.ErpPayable.id == target_id,
            purchase_models.ErpPayable.supplier_id == supplier_id,
        ).with_for_update())
        if target is None:
            raise CustomException("应付核销项目不存在或供应商不一致")
        return target

    async def _allocations(self, document_id, lock=False):
        """读取核销分配明细。"""

        statement = select(models.ErpSettlementAllocation).where(models.ErpSettlementAllocation.document_id == document_id)
        if lock:
            statement = statement.with_for_update()
        return list((await self.db.scalars(statement)).all())

    async def _lock(self, document_id):
        """锁定核销单。"""

        document = await self.db.scalar(select(models.ErpSettlementDocument).where(
            models.ErpSettlementDocument.id == document_id,
            models.ErpSettlementDocument.is_delete == false(),
        ).with_for_update())
        if document is None:
            raise CustomException("核销单不存在")
        return document
