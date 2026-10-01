"""入库单应用服务。"""

import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, false, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exception import CustomException
from apps.erp.finance.services.period import AccountingPeriodService

from ... import models, schemas
from apps.erp.common import MONEY, QTY, quantize
from apps.erp.common.numbering import allocate_document_no
from ..stock import PostingRequest, StockMovement, StockPostingEngine
from .catalog import InboundCatalogMixin
from .read import InboundReadMixin


class InventoryService(InboundCatalogMixin, InboundReadMixin):
    """负责入库单保存、查询、审核、反审核和删除。"""

    def __init__(self, db: AsyncSession, user_id: int | None = None):
        """绑定业务事务和当前操作人。"""

        self.db = db
        self.user_id = user_id

    async def next_receipt_no(self, business_date) -> str:
        """按序衡行锁序列生成入库单号。"""

        return await allocate_document_no(self.db, "inbound", "RK", business_date)

    async def save_receipt(self, data: schemas.InboundReceiptInput, receipt_id: int | None = None):
        """新增或更新草稿入库单及其全部明细。"""

        await AccountingPeriodService(self.db, self.user_id).ensure_open(data.receipt_date, "新增或修改入库单")

        lines = await self._prepare_lines(data)
        if receipt_id:
            receipt = await self.db.scalar(
                select(models.ErpInboundReceipt)
                .where(models.ErpInboundReceipt.id == receipt_id, models.ErpInboundReceipt.is_delete == false())
                .with_for_update()
            )
            if receipt is None:
                raise CustomException("入库单不存在")
            if receipt.status != "draft":
                raise CustomException("只有草稿状态的入库单可以修改")
            if data.receipt_no and data.receipt_no != receipt.receipt_no:
                duplicate = await self.db.scalar(
                    select(models.ErpInboundReceipt.id).where(
                        models.ErpInboundReceipt.receipt_no == data.receipt_no,
                        models.ErpInboundReceipt.id != receipt_id,
                    )
                )
                if duplicate:
                    raise CustomException("入库单号已存在")
                receipt.receipt_no = data.receipt_no
            await self.db.execute(delete(models.ErpInboundReceiptLine).where(models.ErpInboundReceiptLine.receipt_id == receipt_id))
        else:
            receipt_no = data.receipt_no or await self.next_receipt_no(data.receipt_date)
            if await self.db.scalar(select(models.ErpInboundReceipt.id).where(models.ErpInboundReceipt.receipt_no == receipt_no)):
                raise CustomException("入库单号已存在")
            receipt = models.ErpInboundReceipt(receipt_no=receipt_no, created_by_id=self.user_id)
            self.db.add(receipt)
        receipt.receipt_date = data.receipt_date
        receipt.business_type = data.business_type
        receipt.supplier_id = data.supplier_id
        receipt.warehouse_id = data.warehouse_id
        receipt.employee_id = data.employee_id
        receipt.remark = data.remark
        receipt.total_quantity = quantize(sum((item["base_quantity"] for item in lines), Decimal("0")), QTY)
        receipt.total_amount = quantize(sum((item["amount"] for item in lines), Decimal("0")), MONEY)
        await self.db.flush()
        for line in lines:
            self.db.add(models.ErpInboundReceiptLine(receipt_id=receipt.id, **line))
        await self.db.flush()
        return await self.receipt_detail(receipt.id)


    async def approve(self, receipt_id: int):
        """审核入库单并调用统一库存过账引擎。"""

        receipt = await self.db.scalar(
            select(models.ErpInboundReceipt)
            .where(models.ErpInboundReceipt.id == receipt_id, models.ErpInboundReceipt.is_delete == false())
            .with_for_update()
        )
        if receipt is None:
            raise CustomException("入库单不存在")
        if receipt.status == "approved":
            raise CustomException("入库单已审核，请勿重复操作")
        if receipt.status != "draft":
            raise CustomException("当前状态不能审核")
        lines = list(
            (
                await self.db.scalars(
                    select(models.ErpInboundReceiptLine)
                    .where(models.ErpInboundReceiptLine.receipt_id == receipt_id)
                    .order_by(models.ErpInboundReceiptLine.line_no)
                )
            ).all()
        )
        if not lines:
            raise CustomException("入库单没有商品明细")
        now = datetime.now()
        posting_version = receipt.posting_version + 1
        movement_type = StockPostingEngine.inbound_movement_type(receipt.business_type)
        movements = tuple(
            StockMovement(
                movement_type=movement_type,
                business_line_id=line.id,
                movement_role="inbound",
                product_id=line.product_id,
                warehouse_id=line.warehouse_id,
                quantity=Decimal(line.base_quantity),
                amount=Decimal(line.amount),
                batch_no=line.batch_no,
                production_date=line.production_date,
                expiry_date=line.expiry_date,
                serial_numbers=tuple(json.loads(line.serial_numbers) if line.serial_numbers else []),
            )
            for line in lines
        )
        await StockPostingEngine(self.db).post(
            PostingRequest(
                source_type="inbound",
                source_id=receipt.id,
                source_no=receipt.receipt_no,
                posting_version=posting_version,
                movements=movements,
                occurred_at=datetime.combine(receipt.receipt_date, now.time()),
                operator_id=self.user_id,
            )
        )
        receipt.status = "approved"
        receipt.approved_by_id = self.user_id
        receipt.approved_at = now
        receipt.posting_version = posting_version
        await self.db.flush()
        return await self.receipt_detail(receipt.id)

    async def unapprove(self, receipt_id: int):
        """反审核入库单并冲销本次审核产生的库存和成本流水。"""

        receipt = await self.db.scalar(
            select(models.ErpInboundReceipt)
            .where(models.ErpInboundReceipt.id == receipt_id, models.ErpInboundReceipt.is_delete == false())
            .with_for_update()
        )
        if receipt is None or receipt.status != "approved":
            raise CustomException("只有已审核入库单可以反审核")
        await StockPostingEngine(self.db).reverse(
            source_type="inbound",
            source_id=receipt.id,
            posting_version=receipt.posting_version,
            source_no=receipt.receipt_no,
            operator_id=self.user_id,
        )
        receipt.status = "draft"
        receipt.approved_by_id = None
        receipt.approved_at = None
        await self.db.flush()
        return await self.receipt_detail(receipt.id)

    async def delete_receipts(self, ids: list[int]):
        """批量删除尚未审核的草稿入库单。"""

        receipts = list(
            (
                await self.db.scalars(
                    select(models.ErpInboundReceipt).where(
                        models.ErpInboundReceipt.id.in_(ids), models.ErpInboundReceipt.is_delete == false()
                    )
                )
            ).all()
        )
        if len(receipts) != len(set(ids)):
            raise CustomException("部分入库单不存在")
        if any(item.status != "draft" for item in receipts):
            raise CustomException("只能删除草稿状态的入库单")
        await self.db.execute(delete(models.ErpInboundReceiptLine).where(models.ErpInboundReceiptLine.receipt_id.in_(ids)))
        await self.db.execute(delete(models.ErpInboundReceipt).where(models.ErpInboundReceipt.id.in_(ids)))
