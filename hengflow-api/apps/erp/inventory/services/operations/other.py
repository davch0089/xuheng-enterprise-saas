"""其他入库和其他出库应用服务。"""

import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, false, select

from apps.erp.common import MONEY, QTY, quantize
from apps.erp.master import models as master_models
from core.exception import CustomException
from apps.erp.finance.services.period import AccountingPeriodService

from ... import models
from ...operation_schemas import OtherStockOrderInput
from ..stock import MovementType, PostingRequest, StockMovement, StockPostingEngine
from .common import InventoryOperationSupport


class OtherStockOrderService(InventoryOperationSupport):
    """管理其他出入库草稿、审核过账和冲销。"""

    async def save(self, data: OtherStockOrderInput, order_id: int | None = None):
        """新增或修改其他出入库草稿。"""

        await AccountingPeriodService(self.db, self.user_id).ensure_open(data.business_date, "新增或修改其他出入库单")

        await self.active(master_models.ErpWarehouse, data.warehouse_id, "仓库")
        if data.employee_id:
            await self.active(master_models.ErpEmployee, data.employee_id, "经办人")
        prepared = await self.prepare_tracked_lines(data.lines, data.warehouse_id, inbound=data.direction == "inbound")
        if order_id:
            header = await self._lock(order_id)
            if header.status != "draft":
                raise CustomException("只有草稿其他出入库单可以修改")
            await self.db.execute(delete(models.ErpOtherStockOrderLine).where(models.ErpOtherStockOrderLine.order_id == order_id))
        else:
            prefix = "QTRK" if data.direction == "inbound" else "QTCK"
            number = data.order_no or await self.next_no(f"other_{data.direction}", prefix, data.business_date)
            if await self.db.scalar(select(models.ErpOtherStockOrder.id).where(models.ErpOtherStockOrder.order_no == number)):
                raise CustomException("其他出入库单号已存在")
            header = models.ErpOtherStockOrder(order_no=number, created_by_id=self.user_id)
            self.db.add(header)
        header.business_date = data.business_date
        header.direction = data.direction
        header.reason = data.reason
        header.warehouse_id = data.warehouse_id
        header.employee_id = data.employee_id
        header.remark = data.remark
        header.total_quantity = quantize(sum((x["base_quantity"] for x in prepared), Decimal(0)), QTY)
        header.total_amount = quantize(sum((x["amount"] for x in prepared), Decimal(0)), MONEY)
        await self.db.flush()
        for item in prepared:
            self.db.add(models.ErpOtherStockOrderLine(order_id=header.id, **item))
        await self.db.flush()
        return await self.detail(header.id)

    async def approve(self, order_id: int):
        """审核其他出入库单并调用统一库存过账引擎。"""

        header = await self._lock(order_id)
        if header.status != "draft":
            raise CustomException("只有草稿其他出入库单可以审核")
        lines = await self._lines(order_id)
        version = header.posting_version + 1
        now = datetime.now()
        inbound = header.direction == "inbound"
        await StockPostingEngine(self.db).post(
            PostingRequest(
                source_type="other_stock", source_id=header.id, source_no=header.order_no,
                posting_version=version, occurred_at=datetime.combine(header.business_date, now.time()), operator_id=self.user_id,
                movements=tuple(
                    StockMovement(
                        movement_type=MovementType.OTHER_IN if inbound else MovementType.OTHER_OUT,
                        business_line_id=line.id, movement_role=header.direction,
                        product_id=line.product_id, warehouse_id=header.warehouse_id,
                        quantity=Decimal(line.base_quantity), amount=Decimal(line.amount) if inbound else None,
                        batch_no=line.batch_no, production_date=line.production_date,
                        expiry_date=line.expiry_date,
                        serial_numbers=tuple(json.loads(line.serial_numbers) if line.serial_numbers else []),
                    ) for line in lines
                ),
            )
        )
        header.status = "approved"
        header.posting_version = version
        header.approved_by_id = self.user_id
        header.approved_at = now
        await self.db.flush()
        return await self.detail(header.id)

    async def unapprove(self, order_id: int):
        """反审核并冲销其他出入库产生的库存和成本流水。"""

        header = await self._lock(order_id)
        if header.status != "approved":
            raise CustomException("只有已审核其他出入库单可以反审核")
        await StockPostingEngine(self.db).reverse(
            "other_stock", header.id, header.posting_version, header.order_no, self.user_id
        )
        header.status = "draft"
        header.approved_by_id = None
        header.approved_at = None
        await self.db.flush()
        return await self.detail(header.id)

    async def delete(self, ids: list[int]):
        """批量删除其他出入库草稿。"""

        docs = list((await self.db.scalars(select(models.ErpOtherStockOrder).where(models.ErpOtherStockOrder.id.in_(ids), models.ErpOtherStockOrder.is_delete == false()))).all())
        if len(docs) != len(set(ids)) or any(x.status != "draft" for x in docs):
            raise CustomException("只能删除存在的草稿其他出入库单")
        await self.db.execute(delete(models.ErpOtherStockOrderLine).where(models.ErpOtherStockOrderLine.order_id.in_(ids)))
        await self.db.execute(delete(models.ErpOtherStockOrder).where(models.ErpOtherStockOrder.id.in_(ids)))

    async def detail(self, order_id: int):
        """返回其他出入库表头和商品明细。"""

        return await self.operation_detail(models.ErpOtherStockOrder, models.ErpOtherStockOrderLine, "order_id", order_id)

    async def list(self, page: int, limit: int, status=None, keyword=None):
        """分页查询其他出入库单。"""

        return await self.list_documents(models.ErpOtherStockOrder, "business_date", "order_no", page, limit, status, keyword)

    async def _lock(self, order_id: int):
        """锁定其他出入库表头。"""

        header = await self.db.scalar(select(models.ErpOtherStockOrder).where(models.ErpOtherStockOrder.id == order_id, models.ErpOtherStockOrder.is_delete == false()).with_for_update())
        if header is None:
            raise CustomException("其他出入库单不存在")
        return header

    async def _lines(self, order_id: int):
        """按行号读取其他出入库明细。"""

        lines = list((await self.db.scalars(select(models.ErpOtherStockOrderLine).where(models.ErpOtherStockOrderLine.order_id == order_id).order_by(models.ErpOtherStockOrderLine.line_no))).all())
        if not lines:
            raise CustomException("其他出入库单没有商品明细")
        return lines
