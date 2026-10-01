"""一步和两步库存调拨应用服务。"""

import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, false, select

from apps.erp.common import MONEY, QTY, quantize
from apps.erp.master import models as master_models
from core.exception import CustomException
from apps.erp.finance.services.period import AccountingPeriodService

from ... import models
from ...operation_schemas import StockTransferInput
from ..stock import MovementType, PostingRequest, StockMovement, StockPostingEngine
from .common import InventoryOperationSupport


class StockTransferService(InventoryOperationSupport):
    """管理调拨草稿、发运、收货和分阶段冲销。"""

    async def save(self, data: StockTransferInput, transfer_id: int | None = None):
        """新增或修改尚未发运的库存调拨单。"""

        await AccountingPeriodService(self.db, self.user_id).ensure_open(data.transfer_date, "新增或修改库存调拨单")

        await self.active(master_models.ErpWarehouse, data.source_warehouse_id, "调出仓库")
        await self.active(master_models.ErpWarehouse, data.destination_warehouse_id, "调入仓库")
        if data.employee_id:
            await self.active(master_models.ErpEmployee, data.employee_id, "经办人")
        prepared = await self.prepare_tracked_lines(data.lines, data.source_warehouse_id, inbound=False)
        if transfer_id:
            header = await self._lock(transfer_id)
            if header.status != "draft":
                raise CustomException("只有草稿调拨单可以修改")
            await self.db.execute(delete(models.ErpStockTransferLine).where(models.ErpStockTransferLine.transfer_id == transfer_id))
        else:
            number = data.transfer_no or await self.next_no("stock_transfer", "DB", data.transfer_date)
            if await self.db.scalar(select(models.ErpStockTransfer.id).where(models.ErpStockTransfer.transfer_no == number)):
                raise CustomException("调拨单号已存在")
            header = models.ErpStockTransfer(transfer_no=number, created_by_id=self.user_id)
            self.db.add(header)
        header.transfer_date = data.transfer_date
        header.transfer_mode = data.transfer_mode
        header.source_warehouse_id = data.source_warehouse_id
        header.destination_warehouse_id = data.destination_warehouse_id
        header.employee_id = data.employee_id
        header.remark = data.remark
        header.total_quantity = quantize(sum((x["base_quantity"] for x in prepared), Decimal(0)), QTY)
        header.total_amount = 0
        await self.db.flush()
        for item in prepared:
            item.pop("unit_price")
            item.pop("amount")
            self.db.add(models.ErpStockTransferLine(transfer_id=header.id, transfer_amount=0, **item))
        await self.db.flush()
        return await self.detail(header.id)

    async def dispatch(self, transfer_id: int):
        """调出库存；一步调拨继续在同一事务内完成目标仓入库。"""

        header = await self._lock(transfer_id)
        if header.status != "draft":
            raise CustomException("只有草稿调拨单可以发运")
        lines = await self._lines(transfer_id)
        version = header.posting_version + 1
        now = datetime.now()
        ledgers = await StockPostingEngine(self.db).post(
            PostingRequest(
                source_type="transfer_out", source_id=header.id, source_no=header.transfer_no,
                posting_version=version, occurred_at=datetime.combine(header.transfer_date, now.time()), operator_id=self.user_id,
                movements=tuple(self._movement(line, header.source_warehouse_id, MovementType.TRANSFER_OUT, "dispatch") for line in lines),
            )
        )
        ledger_map = {item.business_line_id: item for item in ledgers}
        for line in lines:
            line.transfer_amount = quantize(abs(Decimal(ledger_map[line.id].amount)), MONEY)
        header.total_amount = quantize(sum((Decimal(x.transfer_amount) for x in lines), Decimal(0)), MONEY)
        header.posting_version = version
        header.status = "in_transit"
        header.dispatched_by_id = self.user_id
        header.dispatched_at = now
        await self.db.flush()
        if header.transfer_mode == "one_step":
            await self._receive(header, lines, now)
        return await self.detail(header.id)

    async def receive(self, transfer_id: int):
        """确认两步调拨到货并将在途商品计入目标仓。"""

        header = await self._lock(transfer_id)
        if header.transfer_mode != "two_step" or header.status != "in_transit":
            raise CustomException("只有在途的两步调拨单可以收货")
        await self._receive(header, await self._lines(transfer_id), datetime.now())
        return await self.detail(header.id)

    async def unreceive(self, transfer_id: int):
        """冲销目标仓调拨入库；两步调拨恢复为在途。"""

        header = await self._lock(transfer_id)
        if header.status != "completed":
            raise CustomException("只有已完成调拨单可以撤销收货")
        await StockPostingEngine(self.db).reverse(
            "transfer_in", header.id, header.posting_version, header.transfer_no, self.user_id
        )
        header.received_by_id = None
        header.received_at = None
        header.status = "in_transit"
        await self.db.flush()
        return await self.detail(header.id)

    async def undispatch(self, transfer_id: int):
        """冲销调拨出库；一步调拨会先自动撤销目标仓收货。"""

        header = await self._lock(transfer_id)
        if header.status == "completed" and header.transfer_mode == "one_step":
            await StockPostingEngine(self.db).reverse(
                "transfer_in", header.id, header.posting_version, header.transfer_no, self.user_id
            )
            header.status = "in_transit"
        if header.status != "in_transit":
            raise CustomException("只有在途调拨单可以撤销发运")
        await StockPostingEngine(self.db).reverse(
            "transfer_out", header.id, header.posting_version, header.transfer_no, self.user_id
        )
        header.status = "draft"
        header.dispatched_by_id = None
        header.dispatched_at = None
        header.received_by_id = None
        header.received_at = None
        header.total_amount = 0
        for line in await self._lines(transfer_id):
            line.transfer_amount = 0
        await self.db.flush()
        return await self.detail(header.id)

    async def delete(self, ids: list[int]):
        """批量删除草稿调拨单。"""

        docs = list((await self.db.scalars(select(models.ErpStockTransfer).where(models.ErpStockTransfer.id.in_(ids), models.ErpStockTransfer.is_delete == false()))).all())
        if len(docs) != len(set(ids)) or any(x.status != "draft" for x in docs):
            raise CustomException("只能删除存在的草稿调拨单")
        await self.db.execute(delete(models.ErpStockTransferLine).where(models.ErpStockTransferLine.transfer_id.in_(ids)))
        await self.db.execute(delete(models.ErpStockTransfer).where(models.ErpStockTransfer.id.in_(ids)))

    async def detail(self, transfer_id: int):
        """返回调拨表头和商品明细。"""

        return await self.operation_detail(models.ErpStockTransfer, models.ErpStockTransferLine, "transfer_id", transfer_id)

    async def list(self, page: int, limit: int, status=None, keyword=None):
        """分页查询库存调拨单。"""

        return await self.list_documents(models.ErpStockTransfer, "transfer_date", "transfer_no", page, limit, status, keyword)

    async def _receive(self, header, lines, now):
        """执行目标仓调拨入库并完成单据。"""

        await StockPostingEngine(self.db).post(
            PostingRequest(
                source_type="transfer_in", source_id=header.id, source_no=header.transfer_no,
                posting_version=header.posting_version, occurred_at=datetime.combine(header.transfer_date, now.time()), operator_id=self.user_id,
                movements=tuple(self._movement(line, header.destination_warehouse_id, MovementType.TRANSFER_IN, "receive", Decimal(line.transfer_amount)) for line in lines),
            )
        )
        header.status = "completed"
        header.received_by_id = self.user_id
        header.received_at = now
        await self.db.flush()

    @staticmethod
    def _movement(line, warehouse_id, movement_type, role, amount=None):
        """将调拨明细转换为标准库存移动。"""

        return StockMovement(
            movement_type=movement_type, business_line_id=line.id, movement_role=role,
            product_id=line.product_id, warehouse_id=warehouse_id,
            quantity=Decimal(line.base_quantity), amount=amount, batch_no=line.batch_no,
            production_date=line.production_date, expiry_date=line.expiry_date,
            serial_numbers=tuple(json.loads(line.serial_numbers) if line.serial_numbers else []),
        )

    async def _lock(self, transfer_id: int):
        """锁定调拨单表头。"""

        header = await self.db.scalar(select(models.ErpStockTransfer).where(models.ErpStockTransfer.id == transfer_id, models.ErpStockTransfer.is_delete == false()).with_for_update())
        if header is None:
            raise CustomException("调拨单不存在")
        return header

    async def _lines(self, transfer_id: int):
        """按行号读取调拨明细。"""

        lines = list((await self.db.scalars(select(models.ErpStockTransferLine).where(models.ErpStockTransferLine.transfer_id == transfer_id).order_by(models.ErpStockTransferLine.line_no))).all())
        if not lines:
            raise CustomException("调拨单没有商品明细")
        return lines
