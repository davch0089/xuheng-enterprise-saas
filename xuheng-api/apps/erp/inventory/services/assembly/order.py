"""组装拆卸工单与成本归集服务。"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, false, select

from apps.erp.common import MONEY, QTY, quantize
from apps.erp.master import models as master_models
from core.exception import CustomException
from apps.erp.finance.services.period import AccountingPeriodService

from ... import models
from ...assembly_schemas import AssemblyOrderInput
from ..operations.common import InventoryOperationSupport
from ..stock import MovementType, PostingRequest, StockMovement, StockPostingEngine


class AssemblyOrderService(InventoryOperationSupport):
    """执行BOM展开、子件领用、成品入库及拆卸成本分摊。"""

    async def save(self, data: AssemblyOrderInput, order_id: int | None = None):
        """新增或修改组装拆卸草稿并固化BOM快照。"""

        await AccountingPeriodService(self.db, self.user_id).ensure_open(data.business_date, "新增或修改组装拆卸单")

        bom = await self.db.get(models.ErpBillOfMaterial, data.bom_id)
        if bom is None or bom.is_delete or not bom.is_active:
            raise CustomException("BOM不存在或未启用")
        await self.active(master_models.ErpWarehouse, data.warehouse_id, "作业仓库")
        bom_lines = list((await self.db.scalars(select(models.ErpBillOfMaterialLine).where(models.ErpBillOfMaterialLine.bom_id == bom.id).order_by(models.ErpBillOfMaterialLine.line_no))).all())
        tracking = {x.product_id: x for x in data.tracking}
        scale = Decimal(data.quantity) / Decimal(bom.output_quantity)
        lines = []
        finished = await self.db.get(master_models.ErpProduct, bom.product_id)
        finished_unit = {x["unit_id"]: x for x in await self.catalog.product_units(finished)}[bom.unit_id]
        lines.append(await self._line(1, "finished", finished, bom.unit_id, Decimal(finished_unit["to_base_rate"]), Decimal(data.quantity), tracking.get(finished.id)))
        for index, source in enumerate(bom_lines, 2):
            product = await self.db.get(master_models.ErpProduct, source.component_product_id)
            quantity = Decimal(source.quantity) * scale
            if data.order_type == "assembly":
                quantity *= Decimal(1) + Decimal(source.loss_rate) / Decimal(100)
            lines.append(await self._line(index, "component", product, source.unit_id, Decimal(source.unit_to_base_rate), quantity, tracking.get(product.id)))
        if order_id:
            order = await self._lock(order_id)
            if order.status != "draft":
                raise CustomException("只有草稿工单可以修改")
            await self.db.execute(delete(models.ErpAssemblyOrderLine).where(models.ErpAssemblyOrderLine.order_id == order_id))
        else:
            prefix = "ZZ" if data.order_type == "assembly" else "CX"
            number = data.order_no or await self.next_no(f"{data.order_type}_order", prefix, data.business_date)
            order = models.ErpAssemblyOrder(order_no=number, created_by_id=self.user_id)
            self.db.add(order)
        order.business_date = data.business_date
        order.order_type = data.order_type
        order.bom_id = data.bom_id
        order.warehouse_id = data.warehouse_id
        order.employee_id = data.employee_id
        order.quantity = quantize(Decimal(data.quantity), QTY)
        order.remark = data.remark
        order.total_component_cost = 0
        order.finished_cost = 0
        await self.db.flush()
        for line in lines:
            self.db.add(models.ErpAssemblyOrderLine(order_id=order.id, actual_cost=0, **line))
        await self.db.flush()
        return await self.detail(order.id)

    async def approve(self, order_id: int):
        """审核工单并按类型完成两阶段库存过账和成本归集。"""

        order = await self._lock(order_id)
        if order.status != "draft":
            raise CustomException("只有草稿工单可以审核")
        lines = await self._lines(order_id)
        finished = next(x for x in lines if x.line_role == "finished")
        components = [x for x in lines if x.line_role == "component"]
        version = order.posting_version + 1
        now = datetime.now()
        if order.order_type == "assembly":
            cost = await self._post_out(order, components, "assembly_material", version, now)
            finished.actual_cost = cost
            await self._post_in(order, [(finished, cost)], "assembly_output", version, now)
            order.total_component_cost = cost
            order.finished_cost = cost
        else:
            cost = await self._post_out(order, [finished], "disassembly_finished", version, now)
            allocations = await self._allocate_cost(components, order.warehouse_id, cost)
            await self._post_in(order, allocations, "disassembly_components", version, now)
            for line, amount in allocations:
                line.actual_cost = amount
            finished.actual_cost = cost
            order.finished_cost = cost
            order.total_component_cost = cost
        order.status = "approved"
        order.posting_version = version
        order.approved_by_id = self.user_id
        order.approved_at = now
        await self.db.flush()
        return await self.detail(order.id)

    async def unapprove(self, order_id: int):
        """按入库后出库的逆序冲销组装或拆卸工单。"""

        order = await self._lock(order_id)
        if order.status != "approved":
            raise CustomException("只有已审核工单可以反审核")
        if order.order_type == "assembly":
            sources = ("assembly_output", "assembly_material")
        else:
            sources = ("disassembly_components", "disassembly_finished")
        engine = StockPostingEngine(self.db)
        for source in sources:
            await engine.reverse(source, order.id, order.posting_version, order.order_no, self.user_id)
        order.status = "draft"
        order.approved_by_id = None
        order.approved_at = None
        await self.db.flush()
        return await self.detail(order.id)

    async def _post_out(self, order, lines, source_type, version, now):
        """过账领料或拆卸成品出库并返回实际成本。"""

        ledgers = await StockPostingEngine(self.db).post(PostingRequest(
            source_type=source_type, source_id=order.id, source_no=order.order_no,
            posting_version=version, occurred_at=datetime.combine(order.business_date, now.time()), operator_id=self.user_id,
            movements=tuple(self._movement(x, order.warehouse_id, MovementType.MATERIAL_OUT, f"out_{x.line_role}") for x in lines),
        ))
        mapping = {x.business_line_id: abs(Decimal(x.amount)) for x in ledgers}
        for line in lines:
            line.actual_cost = mapping[line.id]
        return quantize(sum(mapping.values(), Decimal(0)), MONEY)

    async def _post_in(self, order, allocations, source_type, version, now):
        """按分配金额过账成品或拆卸子件入库。"""

        await StockPostingEngine(self.db).post(PostingRequest(
            source_type=source_type, source_id=order.id, source_no=order.order_no,
            posting_version=version, occurred_at=datetime.combine(order.business_date, now.time()), operator_id=self.user_id,
            movements=tuple(self._movement(line, order.warehouse_id, MovementType.PRODUCTION_IN, f"in_{line.line_role}", amount) for line, amount in allocations),
        ))

    async def _allocate_cost(self, lines, warehouse_id, total):
        """按子件当前成本权重分摊拆卸成品成本并保证尾差归零。"""

        weights = []
        for line in lines:
            cost = await self.db.scalar(select(models.ErpInventoryBalance.average_cost).where(models.ErpInventoryBalance.warehouse_id == warehouse_id, models.ErpInventoryBalance.product_id == line.product_id)) or 0
            weights.append(Decimal(line.base_quantity) * Decimal(cost))
        if sum(weights) <= 0:
            weights = [Decimal(x.base_quantity) for x in lines]
        result, allocated = [], Decimal(0)
        weight_total = sum(weights)
        for index, (line, weight) in enumerate(zip(lines, weights)):
            amount = quantize(Decimal(total) - allocated if index == len(lines) - 1 else Decimal(total) * weight / weight_total, MONEY)
            allocated += amount
            result.append((line, amount))
        return result

    @staticmethod
    def _movement(line, warehouse_id, movement_type, role, amount=None):
        """将工单快照行转换为标准库存移动。"""

        return StockMovement(movement_type=movement_type, business_line_id=line.id, movement_role=role,
            product_id=line.product_id, warehouse_id=warehouse_id, quantity=Decimal(line.base_quantity),
            amount=amount, batch_no=line.batch_no, production_date=line.production_date,
            expiry_date=line.expiry_date, serial_numbers=tuple(json.loads(line.serial_numbers) if line.serial_numbers else []))

    async def _line(self, line_no, role, product, unit_id, rate, quantity, tracking):
        """生成并校验工单商品快照行。"""

        base_quantity = quantize(quantity * rate, QTY)
        batch_no = tracking.batch_no if tracking and product.batch_enabled else None
        serials = tracking.serial_numbers if tracking and product.serial_enabled else []
        if product.batch_enabled and not batch_no:
            raise CustomException(f"商品 {product.code} 必须指定批次")
        if product.serial_enabled and (base_quantity != base_quantity.to_integral_value() or len(serials) != int(base_quantity)):
            raise CustomException(f"商品 {product.code} 序列号数量必须等于主单位数量")
        return dict(line_no=line_no, line_role=role, product_id=product.id, unit_id=unit_id,
            unit_to_base_rate=rate, quantity=quantize(quantity, QTY), base_quantity=base_quantity,
            batch_no=batch_no, production_date=tracking.production_date if tracking else None,
            expiry_date=tracking.expiry_date if tracking else None,
            serial_numbers=json.dumps(serials, ensure_ascii=False) if serials else None, remark=None)

    async def detail(self, order_id):
        """返回工单和固化的BOM明细。"""

        return await self.operation_detail(models.ErpAssemblyOrder, models.ErpAssemblyOrderLine, "order_id", order_id)

    async def list(self, page, limit, status=None, keyword=None):
        """分页查询组装拆卸工单。"""

        return await self.list_documents(models.ErpAssemblyOrder, "business_date", "order_no", page, limit, status, keyword)

    async def delete(self, ids):
        """删除工单草稿。"""

        docs = list((await self.db.scalars(select(models.ErpAssemblyOrder).where(models.ErpAssemblyOrder.id.in_(ids), models.ErpAssemblyOrder.is_delete == false()))).all())
        if len(docs) != len(set(ids)) or any(x.status != "draft" for x in docs):
            raise CustomException("只能删除存在的草稿工单")
        await self.db.execute(delete(models.ErpAssemblyOrderLine).where(models.ErpAssemblyOrderLine.order_id.in_(ids)))
        await self.db.execute(delete(models.ErpAssemblyOrder).where(models.ErpAssemblyOrder.id.in_(ids)))

    async def _lock(self, order_id):
        """锁定工单表头。"""

        order = await self.db.scalar(select(models.ErpAssemblyOrder).where(models.ErpAssemblyOrder.id == order_id, models.ErpAssemblyOrder.is_delete == false()).with_for_update())
        if order is None:
            raise CustomException("工单不存在")
        return order

    async def _lines(self, order_id):
        """读取工单快照明细。"""

        return list((await self.db.scalars(select(models.ErpAssemblyOrderLine).where(models.ErpAssemblyOrderLine.order_id == order_id).order_by(models.ErpAssemblyOrderLine.line_no))).all())
