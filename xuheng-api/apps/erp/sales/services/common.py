"""销售单据编号、基础资料校验和金额计算公共能力。"""

from decimal import Decimal

from sqlalchemy import false, select

from apps.erp.common import COST, MONEY, QTY, quantize
from apps.erp.common.numbering import allocate_document_no
from apps.erp.inventory.services.inbound import InventoryService
from apps.erp.master import models as master_models
from apps.erp.master.product_display import sku_snapshot
from core.exception import CustomException


class SalesServiceSupport:
    """为销售应用服务提供编号、资料校验、单位换算和金额计算。"""

    async def next_document_no(self, document_type: str, prefix: str, business_date) -> str:
        """按序衡编号规则生成销售业务单号。"""

        return await allocate_document_no(self.db, document_type, prefix, business_date)

    async def active(self, model, data_id: int, label: str):
        """读取启用的基础资料并在无效时中止业务。"""

        obj = await self.db.scalar(
            select(model).where(
                model.id == data_id,
                model.is_active == True,
                model.is_delete == false(),
            )
        )
        if obj is None:
            raise CustomException(f"{label}不存在或已停用")
        return obj

    async def product_views(self, product_ids) -> dict[int, dict]:
        """批量生成销售单据明细使用的 SKU 展示和单位快照。"""

        products = list((await self.db.scalars(select(master_models.ErpProduct).where(
            master_models.ErpProduct.id.in_(set(product_ids) or {0})
        ))).all())
        catalog = InventoryService(self.db)
        result = {}
        for product in products:
            result[product.id] = {
                **sku_snapshot(product),
                "batch_enabled": product.batch_enabled,
                "serial_enabled": product.serial_enabled,
                "base_unit_id": product.base_unit_id,
                "units": await catalog.product_units(product),
            }
        return result

    async def prepare_lines(
        self, data, *, tracking_required: bool = False, require_batch: bool = True
    ):
        """校验销售商品行并计算主单位数量、折扣和税额。"""

        await self.active(master_models.ErpCustomer, data.customer_id, "客户")
        await self.active(master_models.ErpWarehouse, data.warehouse_id, "默认仓库")
        if data.employee_id:
            await self.active(master_models.ErpEmployee, data.employee_id, "销售员")
        unit_service = InventoryService(self.db)
        prepared = []
        document_serials: set[tuple[int, str]] = set()
        for index, line in enumerate(data.lines, 1):
            warehouse_id = line.warehouse_id or data.warehouse_id
            await self.active(master_models.ErpWarehouse, warehouse_id, f"第{index}行仓库")
            product = await self.active(master_models.ErpProduct, line.product_id, f"第{index}行商品")
            units = {item["unit_id"]: item for item in await unit_service.product_units(product)}
            unit = units.get(line.unit_id)
            if unit is None:
                raise CustomException(f"第{index}行所选单位不属于该商品")
            quantity = quantize(Decimal(line.quantity), QTY)
            rate = Decimal(unit["to_base_rate"])
            base_quantity = quantize(quantity * rate, QTY)
            gross_amount = quantize(quantity * Decimal(line.unit_price), MONEY)
            net_amount = quantize(gross_amount * Decimal(line.discount_rate) / 100, MONEY)
            discount_amount = quantize(gross_amount - net_amount, MONEY)
            tax_amount = quantize(net_amount * Decimal(line.tax_rate) / 100, MONEY)
            tax_inclusive_amount = quantize(net_amount + tax_amount, MONEY)
            serial_numbers = (
                list(line.serial_numbers) if tracking_required and product.serial_enabled else []
            )
            batch_no = line.batch_no if tracking_required and product.batch_enabled else None
            if tracking_required and require_batch and product.batch_enabled and not batch_no:
                raise CustomException(f"第{index}行批次商品必须选择批次")
            if tracking_required and product.serial_enabled:
                if base_quantity != base_quantity.to_integral_value():
                    raise CustomException(f"第{index}行序列号商品数量必须为整数")
                if len(serial_numbers) != int(base_quantity):
                    raise CustomException(f"第{index}行序列号数量必须等于主单位数量")
                for serial in serial_numbers:
                    key = (product.id, serial)
                    if key in document_serials:
                        raise CustomException(f"序列号 {serial} 在本单重复")
                    document_serials.add(key)
            prepared.append(
                {
                    "line_no": index,
                    "product_id": product.id,
                    "warehouse_id": warehouse_id,
                    "unit_id": line.unit_id,
                    "unit_to_base_rate": rate,
                    "quantity": quantity,
                    "base_quantity": base_quantity,
                    "unit_price": quantize(Decimal(line.unit_price), COST),
                    "discount_rate": quantize(Decimal(line.discount_rate), Decimal("0.0001")),
                    "amount": net_amount,
                    "discount_amount": discount_amount,
                    "tax_rate": quantize(Decimal(line.tax_rate), Decimal("0.0001")),
                    "tax_amount": tax_amount,
                    "tax_inclusive_amount": tax_inclusive_amount,
                    "order_line_id": getattr(line, "order_line_id", None),
                    "batch_no": batch_no,
                    "serial_numbers": serial_numbers,
                    "remark": line.remark,
                }
            )
        return prepared

    @staticmethod
    def totals(lines: list[dict]) -> dict:
        """汇总销售单据数量、未税金额、折扣、税额和价税合计。"""

        return {
            "total_quantity": quantize(sum((x["base_quantity"] for x in lines), Decimal(0)), QTY),
            "total_amount": quantize(sum((x["amount"] for x in lines), Decimal(0)), MONEY),
            "discount_amount": quantize(sum((x["discount_amount"] for x in lines), Decimal(0)), MONEY),
            "tax_amount": quantize(sum((x["tax_amount"] for x in lines), Decimal(0)), MONEY),
            "payable_amount": quantize(
                sum((x["tax_inclusive_amount"] for x in lines), Decimal(0)), MONEY
            ),
        }
