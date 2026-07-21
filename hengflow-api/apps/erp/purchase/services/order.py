"""采购订单保存、审核和履约状态服务。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, false, select

from core.exception import CustomException
from apps.erp.finance.services.period import AccountingPeriodService
from .. import models, schemas
from .common import PurchaseServiceSupport


class PurchaseOrderService(PurchaseServiceSupport):
    """管理采购订单草稿、审核、反审核和累计收货。"""

    async def save(self, data: schemas.PurchaseOrderInput, order_id: int | None = None):
        """新增或修改采购订单草稿。"""

        await AccountingPeriodService(self.db, self.user_id).ensure_open(data.business_date, "新增或修改采购订单")

        lines = await self.prepare_lines(data)
        if order_id:
            order = await self._lock(order_id)
            if order.status != "draft":
                raise CustomException("只有草稿采购订单可以修改")
            await self.db.execute(delete(models.ErpPurchaseOrderLine).where(models.ErpPurchaseOrderLine.order_id == order_id))
        else:
            number = data.order_no or await self.next_no("purchase_order", "PO", data.business_date)
            if await self.db.scalar(select(models.ErpPurchaseOrder.id).where(models.ErpPurchaseOrder.order_no == number)):
                raise CustomException("采购订单号已存在")
            order = models.ErpPurchaseOrder(order_no=number, created_by_id=self.user_id)
            self.db.add(order)
        for field in ("business_date", "expected_receipt_date", "supplier_id", "warehouse_id", "employee_id", "remark"):
            setattr(order, field, getattr(data, field))
        for field, value in self.totals(lines).items():
            setattr(order, field, value)
        await self.db.flush()
        for line in lines:
            for key in ("order_line_id", "receipt_line_id", "batch_no", "production_date", "expiry_date", "serial_numbers"):
                line.pop(key, None)
            self.db.add(models.ErpPurchaseOrderLine(order_id=order.id, received_quantity=0, **line))
        await self.db.flush()
        return await self.detail(models.ErpPurchaseOrder, models.ErpPurchaseOrderLine, "order_id", order.id)

    async def approve(self, order_id: int):
        """审核采购订单，使其可被采购收货引用。"""

        order = await self._lock(order_id)
        if order.status != "draft":
            raise CustomException("只有草稿采购订单可以审核")
        order.status = "approved"
        order.posting_version += 1
        order.approved_by_id = self.user_id
        order.approved_at = datetime.now()
        await self.db.flush()
        return await self.detail(models.ErpPurchaseOrder, models.ErpPurchaseOrderLine, "order_id", order.id)

    async def unapprove(self, order_id: int):
        """反审核尚未发生收货的采购订单。"""

        order = await self._lock(order_id)
        if order.status != "approved":
            raise CustomException("只有未收货的已审核采购订单可以反审核")
        lines = await self._lines(order.id, True)
        if any(Decimal(x.received_quantity) for x in lines):
            raise CustomException("采购订单已发生收货，不能反审核")
        order.status = "draft"
        order.approved_by_id = None
        order.approved_at = None
        await self.db.flush()
        return await self.detail(models.ErpPurchaseOrder, models.ErpPurchaseOrderLine, "order_id", order.id)

    async def delete(self, ids: list[int]):
        """删除采购订单草稿。"""

        docs = list((await self.db.scalars(select(models.ErpPurchaseOrder).where(models.ErpPurchaseOrder.id.in_(ids), models.ErpPurchaseOrder.is_delete == false()))).all())
        if len(docs) != len(set(ids)) or any(x.status != "draft" for x in docs):
            raise CustomException("只能删除存在的草稿采购订单")
        await self.db.execute(delete(models.ErpPurchaseOrderLine).where(models.ErpPurchaseOrderLine.order_id.in_(ids)))
        await self.db.execute(delete(models.ErpPurchaseOrder).where(models.ErpPurchaseOrder.id.in_(ids)))

    async def list(self, page, limit, status=None, keyword=None, supplier_id=None):
        """分页查询采购订单。"""

        return await self.list_documents(models.ErpPurchaseOrder, "order_no", page, limit, status, keyword, supplier_id)

    async def _lock(self, order_id):
        """锁定采购订单表头。"""

        order = await self.db.scalar(select(models.ErpPurchaseOrder).where(models.ErpPurchaseOrder.id == order_id, models.ErpPurchaseOrder.is_delete == false()).with_for_update())
        if order is None:
            raise CustomException("采购订单不存在")
        return order

    async def _lines(self, order_id, lock=False):
        """读取采购订单明细。"""

        stmt = select(models.ErpPurchaseOrderLine).where(models.ErpPurchaseOrderLine.order_id == order_id).order_by(models.ErpPurchaseOrderLine.line_no)
        if lock:
            stmt = stmt.with_for_update()
        return list((await self.db.scalars(stmt)).all())
