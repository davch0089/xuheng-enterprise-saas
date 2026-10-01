"""序衡企业隔离、订单履约和数量库存。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import false, select
from sqlalchemy.orm import selectinload

from apps.erp.common.numbering import allocate_document_no
from core.exception import CustomException

from .models import XhOrder, XhOrderLine, XhProduct, XhStock, XhStockLog, XhTenant, XhTenantMember

STATUS_LABELS = {
    "pending_confirm": "待确认",
    "pending_ship": "待发货",
    "completed": "已完成",
    "closed": "已关闭",
}


class XuhengService:
    """当前用户只能操作自己加入的企业。"""

    def __init__(self, db, user):
        self.db = db
        self.user = user

    def _is_admin(self) -> bool:
        return any(role.is_admin for role in self.user.roles)

    async def list_tenants(self):
        sql = select(XhTenant).where(XhTenant.is_delete == false(), XhTenant.is_active == True)
        if not self._is_admin():
            sql = sql.join(XhTenantMember, XhTenantMember.tenant_id == XhTenant.id).where(
                XhTenantMember.user_id == self.user.id,
                XhTenantMember.is_delete == false(),
            )
        rows = (await self.db.scalars(sql.order_by(XhTenant.id.desc()))).all()
        return [self._tenant(row) for row in rows]

    async def create_tenant(self, code: str, name: str):
        code = code.strip()
        exists = await self.db.scalar(select(XhTenant.id).where(XhTenant.code == code, XhTenant.is_delete == false()))
        if exists:
            raise CustomException("企业编码已存在")
        tenant = XhTenant(code=code, name=name.strip(), is_active=True)
        self.db.add(tenant)
        await self.db.flush()
        self.db.add(XhTenantMember(tenant_id=tenant.id, user_id=self.user.id))
        await self.db.flush()
        return self._tenant(tenant)

    async def list_products(self, tenant_id: int):
        await self._require_tenant(tenant_id)
        rows = (await self.db.scalars(
            select(XhProduct)
            .where(XhProduct.tenant_id == tenant_id, XhProduct.is_delete == false())
            .options(selectinload(XhProduct.stock))
            .order_by(XhProduct.id.desc())
        )).all()
        return [self._product(row) for row in rows]

    async def create_product(self, data):
        await self._require_tenant(data.tenant_id)
        exists = await self.db.scalar(select(XhProduct.id).where(
            XhProduct.tenant_id == data.tenant_id,
            XhProduct.code == data.code.strip(),
            XhProduct.is_delete == false(),
        ))
        if exists:
            raise CustomException("该企业下商品编码已存在")
        product = XhProduct(
            tenant_id=data.tenant_id,
            code=data.code.strip(),
            name=data.name.strip(),
            sale_price=data.sale_price,
            is_active=True,
        )
        self.db.add(product)
        await self.db.flush()
        stock = XhStock(tenant_id=data.tenant_id, product_id=product.id, quantity=data.opening_quantity)
        self.db.add(stock)
        if data.opening_quantity:
            self.db.add(XhStockLog(
                tenant_id=data.tenant_id,
                product_id=product.id,
                change_qty=data.opening_quantity,
                reason="opening",
                balance_after=data.opening_quantity,
            ))
        await self.db.flush()
        product.stock = stock
        return self._product(product)

    async def receive_stock(self, tenant_id: int, product_id: int, quantity: int):
        """手工入库，只增加数量。"""

        await self._require_tenant(tenant_id)
        stock = await self._lock_stock(tenant_id, product_id)
        stock.quantity += quantity
        self.db.add(XhStockLog(
            tenant_id=tenant_id,
            product_id=product_id,
            change_qty=quantity,
            reason="receive",
            balance_after=stock.quantity,
        ))
        await self.db.flush()
        return {"product_id": product_id, "quantity": stock.quantity}

    async def list_orders(self, tenant_id: int):
        await self._require_tenant(tenant_id)
        rows = (await self.db.scalars(
            select(XhOrder)
            .where(XhOrder.tenant_id == tenant_id, XhOrder.is_delete == false())
            .options(selectinload(XhOrder.lines))
            .order_by(XhOrder.id.desc())
        )).all()
        return [self._order(row) for row in rows]

    async def create_order(self, data):
        await self._require_tenant(data.tenant_id)
        product_ids = [line.product_id for line in data.lines]
        if len(product_ids) != len(set(product_ids)):
            raise CustomException("同一商品请合并成一行")
        products = {
            item.id: item
            for item in (await self.db.scalars(select(XhProduct).where(
                XhProduct.tenant_id == data.tenant_id,
                XhProduct.id.in_(product_ids),
                XhProduct.is_delete == false(),
                XhProduct.is_active == True,
            ))).all()
        }
        if len(products) != len(product_ids):
            raise CustomException("订单包含不存在或已停用的商品")
        order = XhOrder(
            tenant_id=data.tenant_id,
            order_no=await allocate_document_no(self.db, "xh_order", "OD", date.today()),
            customer_name=data.customer_name.strip(),
            status="pending_confirm",
            remark=(data.remark or "").strip() or None,
        )
        self.db.add(order)
        await self.db.flush()
        for line in data.lines:
            product = products[line.product_id]
            self.db.add(XhOrderLine(
                order_id=order.id,
                product_id=product.id,
                quantity=line.quantity,
                price=product.sale_price,
            ))
        await self.db.flush()
        await self.db.refresh(order, attribute_names=["lines"])
        return self._order(order)

    async def confirm(self, tenant_id: int, order_id: int):
        order = await self._lock_order(tenant_id, order_id)
        self._move(order, "pending_confirm", "pending_ship")
        return self._order(order)

    async def ship(self, tenant_id: int, order_id: int):
        order = await self._lock_order(tenant_id, order_id)
        self._move(order, "pending_ship", "completed")
        for line in sorted(order.lines, key=lambda item: item.product_id):
            stock = await self._lock_stock(tenant_id, line.product_id)
            if stock.quantity < line.quantity:
                raise CustomException("库存数量不足，不能发货")
            stock.quantity -= line.quantity
            self.db.add(XhStockLog(
                tenant_id=tenant_id,
                product_id=line.product_id,
                order_id=order.id,
                change_qty=-line.quantity,
                reason="ship",
                balance_after=stock.quantity,
            ))
        order.shipped_at = datetime.now()
        await self.db.flush()
        return self._order(order)

    async def close(self, tenant_id: int, order_id: int):
        order = await self._lock_order(tenant_id, order_id)
        if order.status not in {"pending_confirm", "pending_ship"}:
            raise CustomException("只有未发货的订单可以关闭")
        order.status = "closed"
        await self.db.flush()
        return self._order(order)

    async def return_order(self, tenant_id: int, order_id: int):
        """整单退货：数量加回，订单关闭。"""

        order = await self._lock_order(tenant_id, order_id)
        self._move(order, "completed", "closed")
        for line in sorted(order.lines, key=lambda item: item.product_id):
            stock = await self._lock_stock(tenant_id, line.product_id)
            stock.quantity += line.quantity
            self.db.add(XhStockLog(
                tenant_id=tenant_id,
                product_id=line.product_id,
                order_id=order.id,
                change_qty=line.quantity,
                reason="return",
                balance_after=stock.quantity,
            ))
        await self.db.flush()
        return self._order(order)

    async def _require_tenant(self, tenant_id: int) -> XhTenant:
        tenant = await self.db.scalar(select(XhTenant).where(
            XhTenant.id == tenant_id, XhTenant.is_delete == false(), XhTenant.is_active == True,
        ))
        if tenant is None:
            raise CustomException("企业不存在")
        if self._is_admin():
            return tenant
        member = await self.db.scalar(select(XhTenantMember.id).where(
            XhTenantMember.tenant_id == tenant_id,
            XhTenantMember.user_id == self.user.id,
            XhTenantMember.is_delete == false(),
        ))
        if member is None:
            raise CustomException("无权访问该企业")
        return tenant

    async def _lock_order(self, tenant_id: int, order_id: int) -> XhOrder:
        await self._require_tenant(tenant_id)
        order = await self.db.scalar(
            select(XhOrder)
            .where(XhOrder.id == order_id, XhOrder.tenant_id == tenant_id, XhOrder.is_delete == false())
            .options(selectinload(XhOrder.lines))
            .with_for_update()
        )
        if order is None:
            raise CustomException("订单不存在")
        return order

    async def _lock_stock(self, tenant_id: int, product_id: int) -> XhStock:
        stock = await self.db.scalar(
            select(XhStock)
            .where(XhStock.tenant_id == tenant_id, XhStock.product_id == product_id, XhStock.is_delete == false())
            .with_for_update()
        )
        if stock is None:
            raise CustomException("商品库存不存在")
        return stock

    @staticmethod
    def _move(order: XhOrder, expected: str, target: str):
        if order.status != expected:
            raise CustomException(f"当前状态是{STATUS_LABELS.get(order.status, order.status)}，不能执行该操作")
        order.status = target

    @staticmethod
    def _tenant(row: XhTenant) -> dict:
        return {"id": row.id, "code": row.code, "name": row.name}

    @staticmethod
    def _product(row: XhProduct) -> dict:
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "code": row.code,
            "name": row.name,
            "sale_price": f"{Decimal(row.sale_price):.2f}",
            "quantity": row.stock.quantity if row.stock else 0,
        }

    @staticmethod
    def _order(row: XhOrder) -> dict:
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "order_no": row.order_no,
            "customer_name": row.customer_name,
            "status": row.status,
            "status_label": STATUS_LABELS.get(row.status, row.status),
            "remark": row.remark,
            "lines": [
                {
                    "product_id": line.product_id,
                    "quantity": line.quantity,
                    "price": f"{Decimal(line.price):.2f}",
                }
                for line in row.lines
            ],
        }
