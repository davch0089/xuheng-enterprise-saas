"""销售出库批次自动分配服务。"""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import false, or_, select

from apps.erp.common import MONEY, QTY, quantize
from apps.erp.inventory import models as inventory_models
from apps.erp.master import models as master_models
from core.exception import CustomException


class SalesBatchAllocator:
    """按未过期批次的 FEFO/FIFO 顺序拆分销售出库明细。"""

    def __init__(self, db):
        """绑定数据库会话并初始化本单批次占用量。"""

        self.db = db
        self._consumed: dict[tuple[int, int, str], Decimal] = defaultdict(Decimal)
        self._batch_cache: dict[tuple[int, int, date], list] = {}

    async def allocate(self, lines: list[dict], business_date: date) -> list[dict]:
        """为全部批次商品分配批次，并在跨批次时拆分明细。"""

        expanded: list[dict] = []
        for line in lines:
            product = await self.db.get(master_models.ErpProduct, line["product_id"])
            if product is None or product.is_delete:
                raise CustomException("销售出库商品不存在")
            if not product.batch_enabled:
                expanded.append({**line, "batch_no": None})
                continue
            if product.serial_enabled:
                allocations = await self._allocate_serial_batches(line, product, business_date)
            else:
                allocations = await self._allocate_quantity_batches(line, product, business_date)
            expanded.extend(self._split_line(line, allocations))
        for line_no, line in enumerate(expanded, 1):
            line["line_no"] = line_no
        return expanded

    async def _available_batches(self, warehouse_id: int, product_id: int, business_date: date):
        """读取指定仓库 SKU 的未过期可用批次并按 FEFO/FIFO 排序。"""

        cache_key = (warehouse_id, product_id, business_date)
        if cache_key not in self._batch_cache:
            batch = inventory_models.ErpInventoryBatchBalance
            self._batch_cache[cache_key] = list(
                (
                    await self.db.scalars(
                        select(batch)
                        .where(
                            batch.warehouse_id == warehouse_id,
                            batch.product_id == product_id,
                            batch.is_delete == false(),
                            batch.quantity > batch.reserved_quantity + batch.frozen_quantity,
                            or_(batch.expiry_date.is_(None), batch.expiry_date >= business_date),
                        )
                        .order_by(
                            batch.expiry_date.is_(None),
                            batch.expiry_date,
                            batch.production_date,
                            batch.id,
                        )
                    )
                ).all()
            )
        return self._batch_cache[cache_key]

    async def _allocate_quantity_batches(self, line: dict, product, business_date: date):
        """按批次余额为普通批次商品分配主单位数量。"""

        remaining = Decimal(line["base_quantity"])
        allocations = []
        rows = await self._available_batches(
            line["warehouse_id"], line["product_id"], business_date
        )
        for batch in rows:
            key = (line["warehouse_id"], line["product_id"], batch.batch_no)
            available = (
                Decimal(batch.quantity)
                - Decimal(batch.reserved_quantity)
                - Decimal(batch.frozen_quantity)
                - self._consumed[key]
            )
            allocated = min(remaining, max(available, Decimal(0)))
            if allocated <= 0:
                continue
            allocations.append((batch.batch_no, allocated, []))
            self._consumed[key] += allocated
            remaining = quantize(remaining - allocated, QTY)
            if remaining <= 0:
                break
        if remaining > 0:
            self._raise_shortage(product, remaining)
        return allocations

    async def _allocate_serial_batches(self, line: dict, product, business_date: date):
        """根据所选序列号的当前批次自动归组，避免人工重复填写批次。"""

        serial_numbers = line["serial_numbers"]
        serial = inventory_models.ErpInventorySerial
        rows = list(
            (
                await self.db.scalars(
                    select(serial).where(
                        serial.product_id == line["product_id"],
                        serial.serial_no.in_(serial_numbers or [""]),
                        serial.is_delete == false(),
                    )
                )
            ).all()
        )
        by_number = {item.serial_no: item for item in rows}
        grouped: dict[str, list[str]] = defaultdict(list)
        for serial_no in serial_numbers:
            item = by_number.get(serial_no)
            if item is None or item.status != "in_stock" or item.warehouse_id != line["warehouse_id"]:
                raise CustomException(f"序列号 {serial_no} 不在当前仓库可用库存中")
            if not item.batch_no:
                raise CustomException(f"序列号 {serial_no} 没有关联批次，不能自动分配")
            grouped[item.batch_no].append(serial_no)

        batches = await self._available_batches(
            line["warehouse_id"], line["product_id"], business_date
        )
        batch_map = {item.batch_no: item for item in batches}
        order_map = {item.batch_no: index for index, item in enumerate(batches)}
        allocations = []
        for batch_no, numbers in sorted(grouped.items(), key=lambda item: order_map.get(item[0], 10**9)):
            batch = batch_map.get(batch_no)
            if batch is None:
                raise CustomException(f"批次 {batch_no} 已过期或没有可用库存，不能自动出库")
            key = (line["warehouse_id"], line["product_id"], batch_no)
            available = (
                Decimal(batch.quantity)
                - Decimal(batch.reserved_quantity)
                - Decimal(batch.frozen_quantity)
                - self._consumed[key]
            )
            quantity = Decimal(len(numbers))
            if quantity > available:
                self._raise_shortage(product, quantity - max(available, Decimal(0)))
            allocations.append((batch_no, quantity, numbers))
            self._consumed[key] += quantity
        return allocations

    @staticmethod
    def _split_line(line: dict, allocations: list[tuple[str, Decimal, list[str]]]):
        """按分配结果拆行，并保证金额及选用单位数量合计不变。"""

        total_base = Decimal(line["base_quantity"])
        rate = Decimal(line["unit_to_base_rate"])
        remaining_quantity = Decimal(line["quantity"])
        amount_fields = ("amount", "discount_amount", "tax_amount", "tax_inclusive_amount")
        remaining_amounts = {field: Decimal(line[field]) for field in amount_fields}
        result = []
        for index, (batch_no, base_quantity, serial_numbers) in enumerate(allocations):
            last = index == len(allocations) - 1
            quantity = (
                remaining_quantity
                if last
                else quantize(Decimal(base_quantity) / rate, QTY)
            )
            item = {
                **line,
                "batch_no": batch_no,
                "serial_numbers": serial_numbers,
                "base_quantity": quantize(Decimal(base_quantity), QTY),
                "quantity": quantity,
            }
            for field in amount_fields:
                value = (
                    remaining_amounts[field]
                    if last
                    else quantize(Decimal(line[field]) * Decimal(base_quantity) / total_base, MONEY)
                )
                item[field] = value
                remaining_amounts[field] -= value
            remaining_quantity -= quantity
            result.append(item)
        return result

    @staticmethod
    def _raise_shortage(product, shortage: Decimal):
        """抛出包含 SKU 和缺口数量的自动分配失败提示。"""

        label = f"{product.code} - {product.name}"
        raise CustomException(
            f"{label} 未过期批次可用库存不足，缺少 {quantize(shortage, QTY)}；"
            "请补充库存、调整数量或改用手动批次"
        )
