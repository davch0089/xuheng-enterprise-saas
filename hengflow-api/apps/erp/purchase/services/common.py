"""采购单据编号、资料校验、金额和详情公共能力。"""

import json
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import false, func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from apps.erp.common import COST, MONEY, QTY, quantize
from apps.erp.inventory.models import ErpDocumentSequence
from apps.erp.inventory.services.inbound import InventoryService
from apps.erp.master import models as master_models
from apps.erp.master.product_display import sku_snapshot
from core.exception import CustomException
from .. import models as purchase_models


class PurchaseServiceSupport:
    """提供采购服务共享的基础资料、单位和金额处理能力。"""

    def __init__(self, db, user_id: int | None = None):
        """绑定当前事务与操作人。"""

        self.db = db
        self.user_id = user_id
        self.catalog = InventoryService(db, user_id)

    async def next_no(self, document_type: str, prefix: str, business_date) -> str:
        """使用数据库原子序列生成采购业务编号。"""

        await self.db.execute(
            mysql_insert(ErpDocumentSequence)
            .values(document_type=document_type, business_date=business_date, current_value=1)
            .on_duplicate_key_update(current_value=ErpDocumentSequence.current_value + 1, update_datetime=func.now())
        )
        value = await self.db.scalar(select(ErpDocumentSequence.current_value).where(
            ErpDocumentSequence.document_type == document_type,
            ErpDocumentSequence.business_date == business_date,
        ))
        return f"{prefix}{business_date:%Y%m%d}{value:04d}"

    async def active(self, model, object_id: int, label: str):
        """读取启用基础资料，不存在或停用时中止。"""

        obj = await self.db.scalar(select(model).where(model.id == object_id, model.is_active == True, model.is_delete == false()))
        if obj is None:
            raise CustomException(f"{label}不存在或已停用")
        return obj

    async def prepare_lines(self, data, *, tracking: bool = False):
        """校验采购商品、单位、批次序列号并计算金额。"""

        await self.active(master_models.ErpSupplier, data.supplier_id, "供应商")
        await self.active(master_models.ErpWarehouse, data.warehouse_id, "默认仓库")
        if data.employee_id:
            await self.active(master_models.ErpEmployee, data.employee_id, "经办人")
        prepared, document_serials = [], set()
        for index, line in enumerate(data.lines, 1):
            warehouse_id = line.warehouse_id or data.warehouse_id
            await self.active(master_models.ErpWarehouse, warehouse_id, f"第{index}行仓库")
            product = await self.active(master_models.ErpProduct, line.product_id, f"第{index}行商品")
            units = {item["unit_id"]: item for item in await self.catalog.product_units(product)}
            unit = units.get(line.unit_id)
            if unit is None:
                raise CustomException(f"第{index}行单位不属于该商品")
            quantity = quantize(Decimal(line.quantity), QTY)
            rate = Decimal(unit["to_base_rate"])
            base_quantity = quantize(quantity * rate, QTY)
            unit_price = quantize(Decimal(line.unit_price), COST)
            amount = quantize(quantity * unit_price, MONEY)
            tax_amount = quantize(amount * Decimal(line.tax_rate) / 100, MONEY)
            batch_no = line.batch_no if tracking and product.batch_enabled else None
            serials = list(line.serial_numbers) if tracking and product.serial_enabled else []
            if tracking and product.batch_enabled and not batch_no:
                raise CustomException(f"第{index}行批次商品必须填写批次")
            if tracking and product.serial_enabled:
                if base_quantity != base_quantity.to_integral_value() or len(serials) != int(base_quantity):
                    raise CustomException(f"第{index}行序列号数量必须等于主单位数量")
                for serial in serials:
                    key = (product.id, serial)
                    if key in document_serials:
                        raise CustomException(f"序列号 {serial} 在本单重复")
                    document_serials.add(key)
            prepared.append(dict(
                line_no=index, product_id=product.id, warehouse_id=warehouse_id,
                unit_id=line.unit_id, unit_to_base_rate=rate, quantity=quantity,
                base_quantity=base_quantity, unit_price=unit_price, amount=amount,
                tax_rate=Decimal(line.tax_rate), tax_amount=tax_amount,
                tax_inclusive_amount=quantize(amount + tax_amount, MONEY),
                order_line_id=line.order_line_id, receipt_line_id=line.receipt_line_id,
                batch_no=batch_no, production_date=line.production_date if batch_no else None,
                expiry_date=line.expiry_date if batch_no else None,
                serial_numbers=json.dumps(serials, ensure_ascii=False) if serials else None,
                remark=line.remark,
            ))
        return prepared

    @staticmethod
    def totals(lines):
        """汇总采购单据主单位数量、未税金额、税额和价税合计。"""

        return {
            "total_quantity": quantize(sum((Decimal(x["base_quantity"]) for x in lines), Decimal(0)), QTY),
            "total_amount": quantize(sum((Decimal(x["amount"]) for x in lines), Decimal(0)), MONEY),
            "tax_amount": quantize(sum((Decimal(x["tax_amount"]) for x in lines), Decimal(0)), MONEY),
            "payable_amount": quantize(sum((Decimal(x["tax_inclusive_amount"]) for x in lines), Decimal(0)), MONEY),
        }

    async def detail(self, header_model, line_model, foreign_key: str, document_id: int):
        """返回采购单据表头、明细及商品展示信息。"""

        header = await self.db.get(header_model, document_id)
        if header is None or header.is_delete:
            raise CustomException("采购单据不存在")
        await self.db.refresh(header)
        lines = list((await self.db.scalars(select(line_model).where(getattr(line_model, foreign_key) == document_id).order_by(line_model.line_no))).all())
        products = {x.id: x for x in (await self.db.scalars(select(master_models.ErpProduct).where(master_models.ErpProduct.id.in_({x.product_id for x in lines} or {0})))).all()}
        result = {key: getattr(header, key) for key in header.get_column_attrs()}
        if isinstance(header, purchase_models.ErpPurchaseReceipt) and header.order_id:
            source_order = await self.db.get(purchase_models.ErpPurchaseOrder, header.order_id)
            result["order_no"] = source_order.order_no if source_order else None
        if isinstance(header, purchase_models.ErpPurchaseReceipt) and header.linked_payment_id:
            linked_payment = await self.db.get(
                purchase_models.ErpPurchasePayment, header.linked_payment_id
            )
            result["linked_payment_no"] = (
                linked_payment.payment_no
                if linked_payment and not linked_payment.is_delete
                else None
            )
        if isinstance(header, purchase_models.ErpPurchaseReturn) and header.receipt_id:
            source_receipt = await self.db.get(purchase_models.ErpPurchaseReceipt, header.receipt_id)
            result["receipt_no"] = source_receipt.receipt_no if source_receipt else None
        result["lines"] = []
        for line in lines:
            await self.db.refresh(line)
            row = {key: getattr(line, key) for key in line.get_column_attrs()}
            if "serial_numbers" in row:
                row["serial_numbers"] = json.loads(row["serial_numbers"]) if row["serial_numbers"] else []
            product = products.get(line.product_id)
            if product:
                row["product"] = {
                    **sku_snapshot(product), "batch_enabled": product.batch_enabled,
                    "serial_enabled": product.serial_enabled, "base_unit_id": product.base_unit_id,
                    "units": await self.catalog.product_units(product),
                }
            result["lines"].append(row)
        return jsonable_encoder(result)

    async def list_documents(self, model, number_field: str, page: int, limit: int, status=None, keyword=None, supplier_id=None):
        """分页查询采购业务单据。"""

        conditions = [model.is_delete == false()]
        if status:
            conditions.append(model.status == status)
        if keyword:
            conditions.append(getattr(model, number_field).like(f"%{keyword.strip()}%"))
        if supplier_id:
            conditions.append(model.supplier_id == supplier_id)
        count = await self.db.scalar(select(func.count(model.id)).where(*conditions))
        rows = list((await self.db.scalars(select(model).where(*conditions).order_by(model.business_date.desc(), model.id.desc()).offset((max(page, 1) - 1) * limit).limit(limit))).all())
        suppliers = {x.id: x.name for x in (await self.db.scalars(select(master_models.ErpSupplier).where(master_models.ErpSupplier.id.in_({x.supplier_id for x in rows} or {0})))).all()}
        source_numbers = {}
        source_field = None
        if model is purchase_models.ErpPurchaseReceipt:
            source_field = "order_id"
            source_rows = list((await self.db.scalars(select(purchase_models.ErpPurchaseOrder).where(
                purchase_models.ErpPurchaseOrder.id.in_({x.order_id for x in rows if x.order_id} or {0})
            ))).all())
            source_numbers = {x.id: x.order_no for x in source_rows}
        elif model is purchase_models.ErpPurchaseReturn:
            source_field = "receipt_id"
            source_rows = list((await self.db.scalars(select(purchase_models.ErpPurchaseReceipt).where(
                purchase_models.ErpPurchaseReceipt.id.in_({x.receipt_id for x in rows if x.receipt_id} or {0})
            ))).all())
            source_numbers = {x.id: x.receipt_no for x in source_rows}

        result = []
        for row in rows:
            item = {
                **{key: getattr(row, key) for key in row.get_column_attrs()},
                "document_no": getattr(row, number_field),
                "supplier_name": suppliers.get(row.supplier_id),
            }
            if source_field:
                item["source_document_no"] = source_numbers.get(getattr(row, source_field))
            result.append(item)
        return jsonable_encoder(result), count or 0
