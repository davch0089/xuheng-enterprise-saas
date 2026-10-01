"""会计期间启用、结账、反结账和成本期末校验。"""

from datetime import date, datetime
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import false, func, or_, select
from sqlalchemy.orm import aliased

from core.exception import CustomException
from .. import models, schemas
from .common import columns


class AccountingPeriodService:
    """控制 ERP 业务日期能否新增、修改、审核或反审核。"""

    def __init__(self, db, user_id: int | None = None):
        """绑定当前事务和操作人。"""

        self.db = db
        self.user_id = user_id

    async def list(self):
        """按开始日期倒序返回全部会计期间。"""

        rows = list((await self.db.scalars(select(models.ErpAccountingPeriod).where(
            models.ErpAccountingPeriod.is_delete == false()
        ).order_by(models.ErpAccountingPeriod.start_date.desc()))).all())
        return jsonable_encoder([columns(item) for item in rows])

    async def create(self, data: schemas.AccountingPeriodInput):
        """启用一个不与现有期间重叠的新会计期间。"""

        overlap = await self.db.scalar(select(models.ErpAccountingPeriod.id).where(
            models.ErpAccountingPeriod.is_delete == false(),
            models.ErpAccountingPeriod.start_date <= data.end_date,
            models.ErpAccountingPeriod.end_date >= data.start_date,
        ).limit(1))
        if overlap is not None:
            raise CustomException("会计期间与现有期间重叠")
        period = models.ErpAccountingPeriod(**data.model_dump(), status="open")
        self.db.add(period)
        await self.db.flush()
        return jsonable_encoder(columns(period))

    async def close(self, period_id: int):
        """通过草稿和成本一致性检查后结账。"""

        period = await self._lock(period_id)
        if period.status != "open":
            raise CustomException("只有已启用期间可以结账")
        await self.db.flush()
        await self._validate_pending_documents(period)
        await self.validate_cost(period.end_date)
        period.status = "closed"
        period.closed_by_id = self.user_id
        period.closed_at = datetime.now()
        period.closing_version += 1
        await self.db.flush()
        return jsonable_encoder(columns(period))

    async def reopen(self, period_id: int):
        """反结账最近一期已结账期间，恢复业务修改能力。"""

        period = await self._lock(period_id)
        if period.status != "closed":
            raise CustomException("只有已结账期间可以反结账")
        later_closed = await self.db.scalar(select(models.ErpAccountingPeriod.id).where(
            models.ErpAccountingPeriod.is_delete == false(),
            models.ErpAccountingPeriod.status == "closed",
            models.ErpAccountingPeriod.end_date > period.end_date,
        ).limit(1))
        if later_closed is not None:
            raise CustomException("存在更晚的已结账期间，请按时间倒序反结账")
        period.status = "open"
        period.closed_by_id = None
        period.closed_at = None
        await self.db.flush()
        return jsonable_encoder(columns(period))

    async def ensure_open(self, business_date: date, action: str = "过账"):
        """启用期间管理后，拒绝未覆盖日期和已结账日期的业务操作。"""

        enabled = await self.db.scalar(select(func.count(models.ErpAccountingPeriod.id)).where(
            models.ErpAccountingPeriod.is_delete == false()
        ))
        if not enabled:
            return
        period = await self.db.scalar(select(models.ErpAccountingPeriod).where(
            models.ErpAccountingPeriod.is_delete == false(),
            models.ErpAccountingPeriod.start_date <= business_date,
            models.ErpAccountingPeriod.end_date >= business_date,
        ))
        if period is None:
            raise CustomException(f"业务日期 {business_date} 不在任何已启用会计期间，禁止{action}")
        if period.status != "open":
            raise CustomException(f"会计期间 {period.period_code} 已结账，禁止{action}")

    async def validate_cost(self, end_date: date):
        """校验库存数量、成本数量、库存价值及负库存暂估是否可结账。"""

        from apps.erp.inventory import models as inventory_models

        stock_rows = list((await self.db.scalars(select(inventory_models.ErpInventoryBalance))).all())
        cost_rows = list((await self.db.scalars(select(inventory_models.ErpInventoryCostBalance))).all())
        stock = {(item.warehouse_id, item.product_id): Decimal(item.quantity) for item in stock_rows}
        cost = {(item.warehouse_id, item.product_id): item for item in cost_rows}
        keys = set(stock) | set(cost)
        errors = []
        for key in keys:
            stock_quantity = stock.get(key, Decimal(0))
            cost_balance = cost.get(key)
            cost_quantity = Decimal(cost_balance.quantity) if cost_balance else Decimal(0)
            if stock_quantity != cost_quantity:
                errors.append(f"仓库{key[0]}/SKU{key[1]}库存{stock_quantity}与成本数量{cost_quantity}不一致")
            if cost_balance and cost_balance.needs_revaluation:
                errors.append(f"仓库{key[0]}/SKU{key[1]}存在待重新计价成本")
        cost_ledger = inventory_models.ErpInventoryCostLedger
        reversal_ledger = aliased(inventory_models.ErpInventoryCostLedger)
        has_reversal = select(reversal_ledger.id).where(
            reversal_ledger.reversal_of_id == cost_ledger.id
        ).exists()
        provisional = await self.db.scalar(select(cost_ledger.id).where(
            cost_ledger.occurred_at <= datetime.combine(end_date, datetime.max.time()),
            cost_ledger.provisional == True,
            cost_ledger.reversal_of_id.is_(None),
            ~has_reversal,
        ).limit(1))
        if provisional is not None:
            errors.append("期间内存在负库存暂估成本流水")
        if errors:
            raise CustomException("成本期末校验失败：" + "；".join(errors[:5]))
        return {"valid": True, "checked_balances": len(keys)}

    async def _validate_pending_documents(self, period):
        """结账前拒绝期间内仍未完成的业务和财务草稿。"""

        from apps.erp.inventory import models as inventory
        from apps.erp.purchase import models as purchase
        from apps.erp.sales import models as sales

        checks = (
            (sales.ErpSalesOrder, sales.ErpSalesOrder.business_date, ("draft",)),
            (sales.ErpSalesDelivery, sales.ErpSalesDelivery.business_date, ("draft",)),
            (sales.ErpSalesReturn, sales.ErpSalesReturn.business_date, ("draft",)),
            (sales.ErpSalesReceipt, sales.ErpSalesReceipt.receipt_date, ("draft",)),
            (purchase.ErpPurchaseOrder, purchase.ErpPurchaseOrder.business_date, ("draft",)),
            (purchase.ErpPurchaseReceipt, purchase.ErpPurchaseReceipt.business_date, ("draft",)),
            (purchase.ErpPurchaseReturn, purchase.ErpPurchaseReturn.business_date, ("draft",)),
            (purchase.ErpPurchasePayment, purchase.ErpPurchasePayment.payment_date, ("draft",)),
            (inventory.ErpInboundReceipt, inventory.ErpInboundReceipt.receipt_date, ("draft",)),
            (inventory.ErpStockTransfer, inventory.ErpStockTransfer.transfer_date, ("draft", "in_transit")),
            (inventory.ErpInventoryCount, inventory.ErpInventoryCount.count_date, ("draft",)),
            (inventory.ErpOtherStockOrder, inventory.ErpOtherStockOrder.business_date, ("draft",)),
            (inventory.ErpAssemblyOrder, inventory.ErpAssemblyOrder.business_date, ("draft",)),
            (models.ErpFundDocument, models.ErpFundDocument.business_date, ("draft",)),
            (models.ErpSettlementDocument, models.ErpSettlementDocument.business_date, ("draft",)),
        )
        for model, date_field, statuses in checks:
            pending = await self.db.scalar(select(model.id).where(
                model.is_delete == false(), date_field >= period.start_date, date_field <= period.end_date,
                model.status.in_(statuses),
            ).limit(1))
            if pending is not None:
                raise CustomException(f"期间内存在未完成的 {model.__table__.comment or model.__tablename__}，不能结账")

    async def _lock(self, period_id: int):
        """锁定并返回指定会计期间。"""

        period = await self.db.scalar(select(models.ErpAccountingPeriod).where(
            models.ErpAccountingPeriod.id == period_id,
            models.ErpAccountingPeriod.is_delete == false(),
        ).with_for_update())
        if period is None:
            raise CustomException("会计期间不存在")
        return period
