"""库存盘点、盘盈和盘亏应用服务。"""

import json
from datetime import datetime
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, false, select

from apps.erp.common import COST, QTY, quantize
from apps.erp.master import models as master_models
from core.exception import CustomException
from apps.erp.finance.services.period import AccountingPeriodService

from ... import models
from ...operation_schemas import InventoryCountInput
from ..stock import MovementType, PostingRequest, StockMovement, StockPostingEngine
from .common import InventoryOperationSupport


class InventoryCountService(InventoryOperationSupport):
    """管理盘点快照、差异确认及盘盈盘亏过账。"""

    async def snapshot(self, warehouse_id: int):
        """生成仓库当前可盘点的商品、批次和序列号快照。"""

        await self.active(master_models.ErpWarehouse, warehouse_id, "盘点仓库")
        balances = list((await self.db.scalars(select(models.ErpInventoryBalance).where(models.ErpInventoryBalance.warehouse_id == warehouse_id, models.ErpInventoryBalance.is_delete == false()).order_by(models.ErpInventoryBalance.product_id))).all())
        products = {x.id: x for x in (await self.db.scalars(select(master_models.ErpProduct).where(master_models.ErpProduct.id.in_({x.product_id for x in balances} or {0}), master_models.ErpProduct.is_delete == false()))).all()}
        batches = list((await self.db.scalars(select(models.ErpInventoryBatchBalance).where(models.ErpInventoryBatchBalance.warehouse_id == warehouse_id, models.ErpInventoryBatchBalance.is_delete == false(), models.ErpInventoryBatchBalance.quantity != 0))).all())
        batch_map: dict[int, list] = {}
        for batch in batches:
            batch_map.setdefault(batch.product_id, []).append(batch)
        rows = []
        for balance in balances:
            product = products.get(balance.product_id)
            if product is None:
                continue
            dimensions = batch_map.get(product.id, []) if product.batch_enabled else [None]
            for batch in dimensions:
                quantity = Decimal(batch.quantity) if batch else Decimal(balance.quantity)
                serials = await self._current_serials(warehouse_id, product.id, batch.batch_no if batch else None)
                rows.append({
                    "product_id": product.id, "product_code": product.code, "product_name": product.name,
                    "barcode": product.barcode, "variant_name": product.variant_name,
                    "specification": product.specification, "unit_id": product.base_unit_id,
                    "batch_enabled": product.batch_enabled, "serial_enabled": product.serial_enabled,
                    "batch_no": batch.batch_no if batch else None,
                    "production_date": batch.production_date if batch else None,
                    "expiry_date": batch.expiry_date if batch else None,
                    "system_quantity": quantity, "counted_quantity": quantity,
                    "system_serial_numbers": serials, "counted_serial_numbers": serials,
                })
        return jsonable_encoder(rows)

    async def save(self, data: InventoryCountInput, count_id: int | None = None):
        """新增或修改盘点草稿并重取账面快照。"""

        await AccountingPeriodService(self.db, self.user_id).ensure_open(data.count_date, "新增或修改库存盘点单")

        await self.active(master_models.ErpWarehouse, data.warehouse_id, "盘点仓库")
        if data.employee_id:
            await self.active(master_models.ErpEmployee, data.employee_id, "盘点人")
        prepared = []
        seen = set()
        for index, item in enumerate(data.lines, 1):
            product = await self.active(master_models.ErpProduct, item.product_id, f"第{index}行商品")
            batch_no = item.batch_no if product.batch_enabled else None
            if product.batch_enabled and not batch_no:
                raise CustomException(f"第{index}行批次商品必须指定批次")
            key = (product.id, batch_no)
            if key in seen:
                raise CustomException("同一商品和批次不能重复盘点")
            seen.add(key)
            system_quantity, production_date, expiry_date = await self._current_quantity(data.warehouse_id, product.id, batch_no)
            system_serials = await self._current_serials(data.warehouse_id, product.id, batch_no) if product.serial_enabled else []
            counted_serials = list(item.counted_serial_numbers) if product.serial_enabled else []
            counted = quantize(Decimal(item.counted_quantity), QTY)
            if product.serial_enabled:
                if counted != counted.to_integral_value() or len(counted_serials) != int(counted):
                    raise CustomException(f"第{index}行实盘序列号数量必须等于实盘数量")
            average_cost = await self.db.scalar(select(models.ErpInventoryBalance.average_cost).where(models.ErpInventoryBalance.warehouse_id == data.warehouse_id, models.ErpInventoryBalance.product_id == product.id, models.ErpInventoryBalance.is_delete == false())) or 0
            prepared.append(dict(
                line_no=index, product_id=product.id, unit_id=product.base_unit_id,
                system_quantity=system_quantity, counted_quantity=counted,
                difference_quantity=quantize(counted - system_quantity, QTY),
                snapshot_unit_cost=quantize(Decimal(average_cost), COST), batch_no=batch_no,
                production_date=production_date, expiry_date=expiry_date,
                system_serial_numbers=json.dumps(system_serials, ensure_ascii=False) if system_serials else None,
                counted_serial_numbers=json.dumps(counted_serials, ensure_ascii=False) if counted_serials else None,
                remark=item.remark,
            ))
        if count_id:
            header = await self._lock(count_id)
            if header.status != "draft":
                raise CustomException("只有草稿盘点单可以修改")
            await self.db.execute(delete(models.ErpInventoryCountLine).where(models.ErpInventoryCountLine.count_id == count_id))
        else:
            number = data.count_no or await self.next_no("inventory_count", "PD", data.count_date)
            if await self.db.scalar(select(models.ErpInventoryCount.id).where(models.ErpInventoryCount.count_no == number)):
                raise CustomException("盘点单号已存在")
            header = models.ErpInventoryCount(count_no=number, created_by_id=self.user_id)
            self.db.add(header)
        header.count_date = data.count_date
        header.warehouse_id = data.warehouse_id
        header.employee_id = data.employee_id
        header.remark = data.remark
        header.total_lines = len(prepared)
        header.total_system_quantity = quantize(sum((x["system_quantity"] for x in prepared), Decimal(0)), QTY)
        header.total_counted_quantity = quantize(sum((x["counted_quantity"] for x in prepared), Decimal(0)), QTY)
        header.total_gain_quantity = quantize(sum((max(x["difference_quantity"], Decimal(0)) for x in prepared), Decimal(0)), QTY)
        header.total_loss_quantity = quantize(sum((max(-x["difference_quantity"], Decimal(0)) for x in prepared), Decimal(0)), QTY)
        await self.db.flush()
        for item in prepared:
            self.db.add(models.ErpInventoryCountLine(count_id=header.id, **item))
        await self.db.flush()
        return await self.detail(header.id)

    async def approve(self, count_id: int):
        """确认快照未失效后按差异过账盘盈或盘亏。"""

        header = await self._lock(count_id)
        if header.status != "draft":
            raise CustomException("只有草稿盘点单可以审核")
        lines = await self._lines(count_id)
        movements = []
        for line in lines:
            current_quantity, _, _ = await self._current_quantity(header.warehouse_id, line.product_id, line.batch_no)
            current_serials = await self._current_serials(header.warehouse_id, line.product_id, line.batch_no)
            system_serials = json.loads(line.system_serial_numbers) if line.system_serial_numbers else []
            if current_quantity != Decimal(line.system_quantity) or set(current_serials) != set(system_serials):
                raise CustomException("盘点快照后库存已变化，请重新保存盘点单后再审核")
            difference = Decimal(line.difference_quantity)
            counted_serials = json.loads(line.counted_serial_numbers) if line.counted_serial_numbers else []
            serial_gains = tuple(sorted(set(counted_serials) - set(system_serials)))
            serial_losses = tuple(sorted(set(system_serials) - set(counted_serials)))
            if system_serials or counted_serials:
                if serial_losses:
                    movements.append(StockMovement(
                        movement_type=MovementType.STOCK_LOSS, business_line_id=line.id,
                        movement_role="serial_loss", product_id=line.product_id,
                        warehouse_id=header.warehouse_id, quantity=Decimal(len(serial_losses)),
                        batch_no=line.batch_no, serial_numbers=serial_losses,
                    ))
                if serial_gains:
                    movements.append(StockMovement(
                        movement_type=MovementType.STOCK_GAIN, business_line_id=line.id,
                        movement_role="serial_gain", product_id=line.product_id,
                        warehouse_id=header.warehouse_id, quantity=Decimal(len(serial_gains)),
                        unit_cost=Decimal(line.snapshot_unit_cost), batch_no=line.batch_no,
                        production_date=line.production_date, expiry_date=line.expiry_date,
                        serial_numbers=serial_gains,
                    ))
                continue
            if not difference:
                continue
            movements.append(StockMovement(
                movement_type=MovementType.STOCK_GAIN if difference > 0 else MovementType.STOCK_LOSS,
                business_line_id=line.id, movement_role="gain" if difference > 0 else "loss",
                product_id=line.product_id, warehouse_id=header.warehouse_id, quantity=abs(difference),
                unit_cost=Decimal(line.snapshot_unit_cost) if difference > 0 else None,
                batch_no=line.batch_no, production_date=line.production_date, expiry_date=line.expiry_date,
                serial_numbers=(),
            ))
        version = header.posting_version + 1
        now = datetime.now()
        if movements:
            await StockPostingEngine(self.db).post(PostingRequest(
                source_type="inventory_count", source_id=header.id, source_no=header.count_no,
                posting_version=version, movements=tuple(movements), occurred_at=datetime.combine(header.count_date, now.time()), operator_id=self.user_id,
            ))
        header.status = "approved"
        header.posting_version = version
        header.approved_by_id = self.user_id
        header.approved_at = now
        await self.db.flush()
        return await self.detail(header.id)

    async def unapprove(self, count_id: int):
        """反审核盘点并冲销盘盈盘亏；无差异盘点无需冲销流水。"""

        header = await self._lock(count_id)
        if header.status != "approved":
            raise CustomException("只有已审核盘点单可以反审核")
        ledger_id = await self.db.scalar(select(models.ErpInventoryLedger.id).where(models.ErpInventoryLedger.business_type == "inventory_count", models.ErpInventoryLedger.business_id == header.id, models.ErpInventoryLedger.posting_version == header.posting_version, models.ErpInventoryLedger.reversal_of_id.is_(None)).limit(1))
        if ledger_id:
            await StockPostingEngine(self.db).reverse("inventory_count", header.id, header.posting_version, header.count_no, self.user_id)
        header.status = "draft"
        header.approved_by_id = None
        header.approved_at = None
        await self.db.flush()
        return await self.detail(header.id)

    async def delete(self, ids: list[int]):
        """批量删除盘点草稿。"""

        docs = list((await self.db.scalars(select(models.ErpInventoryCount).where(models.ErpInventoryCount.id.in_(ids), models.ErpInventoryCount.is_delete == false()))).all())
        if len(docs) != len(set(ids)) or any(x.status != "draft" for x in docs):
            raise CustomException("只能删除存在的草稿盘点单")
        await self.db.execute(delete(models.ErpInventoryCountLine).where(models.ErpInventoryCountLine.count_id.in_(ids)))
        await self.db.execute(delete(models.ErpInventoryCount).where(models.ErpInventoryCount.id.in_(ids)))

    async def detail(self, count_id: int):
        """返回盘点表头和差异明细。"""

        return await self.operation_detail(models.ErpInventoryCount, models.ErpInventoryCountLine, "count_id", count_id)

    async def list(self, page: int, limit: int, status=None, keyword=None):
        """分页查询盘点单。"""

        return await self.list_documents(models.ErpInventoryCount, "count_date", "count_no", page, limit, status, keyword)

    async def _current_quantity(self, warehouse_id: int, product_id: int, batch_no: str | None):
        """读取商品或商品批次的当前账面数量及日期。"""

        if batch_no:
            batch = await self.db.scalar(select(models.ErpInventoryBatchBalance).where(models.ErpInventoryBatchBalance.warehouse_id == warehouse_id, models.ErpInventoryBatchBalance.product_id == product_id, models.ErpInventoryBatchBalance.batch_no == batch_no, models.ErpInventoryBatchBalance.is_delete == false()))
            return (Decimal(batch.quantity), batch.production_date, batch.expiry_date) if batch else (Decimal(0), None, None)
        quantity = await self.db.scalar(select(models.ErpInventoryBalance.quantity).where(models.ErpInventoryBalance.warehouse_id == warehouse_id, models.ErpInventoryBalance.product_id == product_id, models.ErpInventoryBalance.is_delete == false()))
        return Decimal(quantity or 0), None, None

    async def _current_serials(self, warehouse_id: int, product_id: int, batch_no: str | None):
        """读取当前仓库和批次内处于库存状态的序列号。"""

        conditions = [models.ErpInventorySerial.warehouse_id == warehouse_id, models.ErpInventorySerial.product_id == product_id, models.ErpInventorySerial.status == "in_stock"]
        conditions.append(models.ErpInventorySerial.batch_no == batch_no if batch_no else models.ErpInventorySerial.batch_no.is_(None))
        return list((await self.db.scalars(select(models.ErpInventorySerial.serial_no).where(*conditions).order_by(models.ErpInventorySerial.serial_no))).all())

    async def _lock(self, count_id: int):
        """锁定盘点单表头。"""

        header = await self.db.scalar(select(models.ErpInventoryCount).where(models.ErpInventoryCount.id == count_id, models.ErpInventoryCount.is_delete == false()).with_for_update())
        if header is None:
            raise CustomException("盘点单不存在")
        return header

    async def _lines(self, count_id: int):
        """按行号读取盘点明细。"""

        lines = list((await self.db.scalars(select(models.ErpInventoryCountLine).where(models.ErpInventoryCountLine.count_id == count_id).order_by(models.ErpInventoryCountLine.line_no))).all())
        if not lines:
            raise CustomException("盘点单没有明细")
        return lines
