"""采购退货、库存发出和红字应付服务。"""

import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, false, select

from apps.erp.common import MONEY, quantize
from apps.erp.inventory.services.stock import MovementType, PostingRequest, StockMovement, StockPostingEngine
from core.exception import CustomException
from apps.erp.finance.services.period import AccountingPeriodService
from .. import models, schemas
from .common import PurchaseServiceSupport
from .payable import PayableService


class PurchaseReturnService(PurchaseServiceSupport):
    """管理采购退货并同步原收货可退量、库存和应付。"""

    async def save(self, data: schemas.PurchaseReturnInput, return_id: int | None = None):
        """新增或修改采购退货草稿，并沿用原收货价格。"""

        await AccountingPeriodService(self.db, self.user_id).ensure_open(data.business_date, "新增或修改采购退货单")

        receipt = await self.db.get(models.ErpPurchaseReceipt, data.receipt_id)
        if receipt is None or receipt.is_delete or receipt.status != "approved":
            raise CustomException("原采购收货单不存在或未审核")
        if receipt.supplier_id != data.supplier_id:
            raise CustomException("退货供应商与原收货单不一致")
        lines = await self.prepare_lines(data, tracking=True)
        sources = {x.id: x for x in (await self.db.scalars(select(models.ErpPurchaseReceiptLine).where(models.ErpPurchaseReceiptLine.receipt_id == receipt.id))).all()}
        for line in lines:
            source = sources.get(line["receipt_line_id"])
            if source is None or source.product_id != line["product_id"] or source.unit_id != line["unit_id"]:
                raise CustomException("采购退货行与原收货行不匹配")
            if Decimal(line["base_quantity"]) > Decimal(source.base_quantity) - Decimal(source.returned_quantity):
                raise CustomException("采购退货数量超过原收货可退数量")
            line["unit_price"] = Decimal(source.unit_price)
            line["amount"] = quantize(Decimal(source.unit_price) * Decimal(line["quantity"]), MONEY)
            line["tax_rate"] = Decimal(source.tax_rate)
            line["tax_amount"] = quantize(line["amount"] * line["tax_rate"] / 100, MONEY)
            line["tax_inclusive_amount"] = quantize(line["amount"] + line["tax_amount"], MONEY)
            if source.batch_no and line["batch_no"] != source.batch_no:
                raise CustomException("采购退货批次必须与原收货批次一致")
        if return_id:
            document = await self._lock(return_id)
            if document.status != "draft":
                raise CustomException("只有草稿采购退货单可以修改")
            await self.db.execute(delete(models.ErpPurchaseReturnLine).where(models.ErpPurchaseReturnLine.return_id == return_id))
        else:
            number = data.return_no or await self.next_no("purchase_return", "PT", data.business_date)
            document = models.ErpPurchaseReturn(return_no=number, created_by_id=self.user_id)
            self.db.add(document)
        for field in ("business_date", "receipt_id", "supplier_id", "warehouse_id", "employee_id", "remark"):
            setattr(document, field, getattr(data, field))
        for field, value in self.totals(lines).items():
            setattr(document, field, value)
        await self.db.flush()
        for line in lines:
            for key in ("order_line_id", "production_date", "expiry_date"):
                line.pop(key, None)
            self.db.add(models.ErpPurchaseReturnLine(return_id=document.id, **line))
        await self.db.flush()
        return await self.detail(models.ErpPurchaseReturn, models.ErpPurchaseReturnLine, "return_id", document.id)

    async def approve(self, return_id: int):
        """审核退货并减少库存和供应商应付。"""

        document = await self._lock(return_id)
        if document.status != "draft":
            raise CustomException("只有草稿采购退货单可以审核")
        lines = await self._lines(document.id, True)
        await self._validate_remaining(document, lines)
        version, now = document.posting_version + 1, datetime.now()
        await StockPostingEngine(self.db).post(PostingRequest(
            source_type="purchase_return", source_id=document.id, source_no=document.return_no,
            posting_version=version, occurred_at=datetime.combine(document.business_date, now.time()), operator_id=self.user_id,
            movements=tuple(StockMovement(
                movement_type=MovementType.PURCHASE_RETURN, business_line_id=line.id,
                movement_role="purchase_return", product_id=line.product_id,
                warehouse_id=line.warehouse_id, quantity=Decimal(line.base_quantity),
                batch_no=line.batch_no,
                serial_numbers=tuple(json.loads(line.serial_numbers) if line.serial_numbers else []),
            ) for line in lines),
        ))
        document.status = "approved"
        document.posting_version = version
        document.approved_by_id = self.user_id
        document.approved_at = now
        await self._apply_returned(lines, Decimal(1))
        await self.db.flush()
        await PayableService(self.db, self.user_id).recognize_return(document)
        return await self.detail(models.ErpPurchaseReturn, models.ErpPurchaseReturnLine, "return_id", document.id)

    async def unapprove(self, return_id: int):
        """反审核采购退货并恢复库存和应付。"""

        document = await self._lock(return_id)
        if document.status != "approved":
            raise CustomException("只有已审核采购退货单可以反审核")
        lines = await self._lines(document.id, True)
        await PayableService(self.db, self.user_id).reverse_return(document)
        await StockPostingEngine(self.db).reverse("purchase_return", document.id, document.posting_version, document.return_no, self.user_id)
        await self._apply_returned(lines, Decimal(-1))
        document.status = "draft"
        document.approved_by_id = None
        document.approved_at = None
        await self.db.flush()
        return await self.detail(models.ErpPurchaseReturn, models.ErpPurchaseReturnLine, "return_id", document.id)

    async def delete(self, ids):
        """删除采购退货草稿。"""

        docs = list((await self.db.scalars(select(models.ErpPurchaseReturn).where(models.ErpPurchaseReturn.id.in_(ids), models.ErpPurchaseReturn.is_delete == false()))).all())
        if len(docs) != len(set(ids)) or any(x.status != "draft" for x in docs):
            raise CustomException("只能删除存在的草稿采购退货单")
        await self.db.execute(delete(models.ErpPurchaseReturnLine).where(models.ErpPurchaseReturnLine.return_id.in_(ids)))
        await self.db.execute(delete(models.ErpPurchaseReturn).where(models.ErpPurchaseReturn.id.in_(ids)))

    async def list(self, page, limit, status=None, keyword=None, supplier_id=None):
        """分页查询采购退货单。"""

        return await self.list_documents(models.ErpPurchaseReturn, "return_no", page, limit, status, keyword, supplier_id)

    async def _validate_remaining(self, document, lines):
        """锁定原收货行并校验并发可退数量。"""

        requested = {}
        for line in lines:
            requested[line.receipt_line_id] = requested.get(line.receipt_line_id, Decimal(0)) + Decimal(line.base_quantity)
        sources = {
            source.id: source
            for source in (
                await self.db.scalars(
                    select(models.ErpPurchaseReceiptLine)
                    .where(
                        models.ErpPurchaseReceiptLine.id.in_(requested),
                        models.ErpPurchaseReceiptLine.receipt_id == document.receipt_id,
                    )
                    .with_for_update()
                )
            ).all()
        }
        for line_id, quantity in requested.items():
            source = sources.get(line_id)
            if source is None or Decimal(source.returned_quantity) + quantity > Decimal(source.base_quantity):
                raise CustomException("采购退货数量超过原收货可退数量")

    async def _apply_returned(self, lines, direction):
        """增加或撤销原收货行累计退货数量。"""

        for line in lines:
            source = await self.db.scalar(select(models.ErpPurchaseReceiptLine).where(models.ErpPurchaseReceiptLine.id == line.receipt_line_id).with_for_update())
            source.returned_quantity = Decimal(source.returned_quantity) + direction * Decimal(line.base_quantity)

    async def _lock(self, return_id):
        """锁定采购退货单。"""

        document = await self.db.scalar(select(models.ErpPurchaseReturn).where(models.ErpPurchaseReturn.id == return_id, models.ErpPurchaseReturn.is_delete == false()).with_for_update())
        if document is None:
            raise CustomException("采购退货单不存在")
        return document

    async def _lines(self, return_id, lock=False):
        """读取采购退货明细。"""

        stmt = select(models.ErpPurchaseReturnLine).where(models.ErpPurchaseReturnLine.return_id == return_id).order_by(models.ErpPurchaseReturnLine.line_no)
        if lock:
            stmt = stmt.with_for_update()
        return list((await self.db.scalars(stmt)).all())
