"""销售订单保存、审核和库存预留服务。"""

from datetime import datetime
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, false, select

from core.exception import CustomException
from apps.erp.finance.services.period import AccountingPeriodService

from .. import models, schemas
from .common import SalesServiceSupport
from .reservation import StockReservationService


class SalesOrderService(SalesServiceSupport):
    """负责销售订单草稿、审核、反审核和库存预留。"""

    def __init__(self, db, user_id: int | None = None):
        """绑定当前业务事务和操作人。"""

        self.db = db
        self.user_id = user_id
        self.reservations = StockReservationService(db)

    async def save(self, data: schemas.SalesOrderInput, order_id: int | None = None):
        """新增或修改草稿销售订单。"""

        await AccountingPeriodService(self.db, self.user_id).ensure_open(data.business_date, "新增或修改销售订单")

        prepared = await self.prepare_lines(data)
        if order_id:
            order = await self._lock(order_id)
            if order.status != "draft":
                raise CustomException("只有草稿销售订单可以修改")
            await self.db.execute(
                delete(models.ErpSalesOrderLine).where(
                    models.ErpSalesOrderLine.order_id == order_id
                )
            )
            if data.order_no and data.order_no != order.order_no:
                await self._ensure_number(data.order_no, order_id)
                order.order_no = data.order_no
        else:
            number = data.order_no or await self.next_document_no(
                "sales_order", "SO", data.business_date
            )
            await self._ensure_number(number)
            order = models.ErpSalesOrder(order_no=number, created_by_id=self.user_id)
            self.db.add(order)
        for field in (
            "business_date",
            "expected_delivery_date",
            "customer_id",
            "warehouse_id",
            "employee_id",
            "delivery_address",
            "remark",
        ):
            setattr(order, field, getattr(data, field))
        for field, value in self.totals(prepared).items():
            setattr(order, field, value)
        await self.db.flush()
        for line in prepared:
            line.pop("order_line_id", None)
            line.pop("batch_no", None)
            line.pop("serial_numbers", None)
            self.db.add(
                models.ErpSalesOrderLine(
                    order_id=order.id,
                    delivered_quantity=0,
                    **line,
                )
            )
        await self.db.flush()
        return await self.detail(order.id)

    async def approve(self, order_id: int):
        """审核销售订单并预留全部未交库存。"""

        order = await self._lock(order_id)
        if order.status != "draft":
            raise CustomException("只有草稿销售订单可以审核")
        lines = await self._lines(order.id, lock=True)
        if not lines:
            raise CustomException("销售订单没有商品明细")
        await self.reservations.reserve_order(order, lines)
        order.status = "approved"
        order.posting_version += 1
        order.approved_by_id = self.user_id
        order.approved_at = datetime.now()
        await self.db.flush()
        return await self.detail(order.id)

    async def unapprove(self, order_id: int):
        """释放未使用预留并将未履约订单恢复为草稿。"""

        order = await self._lock(order_id)
        if order.status != "approved":
            raise CustomException("只有未出库的已审核订单可以反审核")
        lines = await self._lines(order.id, lock=True)
        if any(Decimal(line.delivered_quantity) for line in lines):
            raise CustomException("销售订单已发生出库，不能反审核")
        await self.reservations.cancel_order(order.id)
        order.status = "draft"
        order.approved_by_id = None
        order.approved_at = None
        await self.db.flush()
        return await self.detail(order.id)

    async def delete(self, ids: list[int]):
        """批量删除草稿销售订单及其明细。"""

        orders = list(
            (
                await self.db.scalars(
                    select(models.ErpSalesOrder).where(
                        models.ErpSalesOrder.id.in_(ids),
                        models.ErpSalesOrder.is_delete == false(),
                    )
                )
            ).all()
        )
        if len(orders) != len(set(ids)) or any(item.status != "draft" for item in orders):
            raise CustomException("只能删除存在的草稿销售订单")
        await self.db.execute(
            delete(models.ErpSalesOrderLine).where(models.ErpSalesOrderLine.order_id.in_(ids))
        )
        await self.db.execute(delete(models.ErpSalesOrder).where(models.ErpSalesOrder.id.in_(ids)))

    async def detail(self, order_id: int):
        """返回销售订单及明细。"""

        order = await self.db.scalar(
            select(models.ErpSalesOrder).where(
                models.ErpSalesOrder.id == order_id,
                models.ErpSalesOrder.is_delete == false(),
            )
        )
        if order is None:
            raise CustomException("销售订单不存在")
        result = {key: getattr(order, key) for key in order.get_column_attrs()}
        lines = list(await self._lines(order_id))
        products = await self.product_views(line.product_id for line in lines)
        result["lines"] = [
            {
                **{key: getattr(line, key) for key in line.get_column_attrs()},
                "product": products.get(line.product_id),
            }
            for line in lines
        ]
        return jsonable_encoder(result)

    async def _lock(self, order_id: int):
        """锁定销售订单表头。"""

        order = await self.db.scalar(
            select(models.ErpSalesOrder)
            .where(
                models.ErpSalesOrder.id == order_id,
                models.ErpSalesOrder.is_delete == false(),
            )
            .with_for_update()
        )
        if order is None:
            raise CustomException("销售订单不存在")
        return order

    async def _lines(self, order_id: int, lock: bool = False):
        """读取销售订单明细并可选加行锁。"""

        sql = select(models.ErpSalesOrderLine).where(
            models.ErpSalesOrderLine.order_id == order_id
        ).order_by(models.ErpSalesOrderLine.line_no)
        if lock:
            sql = sql.with_for_update()
        return list((await self.db.scalars(sql)).all())

    async def _ensure_number(self, number: str, exclude_id: int | None = None):
        """确保销售订单号唯一。"""

        conditions = [models.ErpSalesOrder.order_no == number]
        if exclude_id:
            conditions.append(models.ErpSalesOrder.id != exclude_id)
        if await self.db.scalar(select(models.ErpSalesOrder.id).where(*conditions)):
            raise CustomException("销售订单号已存在")
