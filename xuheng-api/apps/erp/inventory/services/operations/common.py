"""库存作业服务共享的编号、基础资料和商品校验。"""

import json
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import false, func, select

from apps.erp.common import COST, MONEY, QTY, quantize
from apps.erp.common.numbering import allocate_document_no
from apps.erp.master import models as master_models
from apps.erp.master.product_display import sku_snapshot
from core.exception import CustomException

from ... import models
from ..inbound import InventoryService


class InventoryOperationSupport:
    """为库存作业提供通用数据访问和明细标准化能力。"""

    def __init__(self, db, user_id: int | None = None):
        """绑定当前事务和操作人。"""

        self.db = db
        self.user_id = user_id
        self.catalog = InventoryService(db, user_id)

    async def next_no(self, document_type: str, prefix: str, business_date) -> str:
        """按序衡行锁序列生成库存作业单号。"""

        return await allocate_document_no(self.db, document_type, prefix, business_date)

    async def active(self, model, object_id: int, label: str):
        """读取启用且未删除的基础资料。"""

        obj = await self.db.scalar(
            select(model).where(model.id == object_id, model.is_active == True, model.is_delete == false())
        )
        if obj is None:
            raise CustomException(f"{label}不存在或已停用")
        return obj

    async def prepare_tracked_lines(self, input_lines, warehouse_id: int, inbound: bool | None = None):
        """校验商品单位和跟踪属性并转换为主单位数量。"""

        prepared = []
        document_serials: set[tuple[int, str]] = set()
        for index, item in enumerate(input_lines, 1):
            product = await self.active(master_models.ErpProduct, item.product_id, f"第{index}行商品")
            units = {unit["unit_id"]: unit for unit in await self.catalog.product_units(product)}
            unit = units.get(item.unit_id)
            if unit is None:
                raise CustomException(f"第{index}行单位不属于该商品")
            quantity = quantize(Decimal(item.quantity), QTY)
            base_quantity = quantize(quantity * Decimal(unit["to_base_rate"]), QTY)
            serials = list(item.serial_numbers) if product.serial_enabled else []
            batch_no = item.batch_no if product.batch_enabled else None
            if product.batch_enabled and not batch_no:
                raise CustomException(f"第{index}行批次商品必须填写批次号")
            if product.serial_enabled:
                if base_quantity != base_quantity.to_integral_value() or len(serials) != int(base_quantity):
                    raise CustomException(f"第{index}行序列号数量必须等于主单位数量")
                for serial in serials:
                    key = (product.id, serial)
                    if key in document_serials:
                        raise CustomException(f"序列号 {serial} 在本单重复")
                    document_serials.add(key)
            unit_price = quantize(Decimal(item.unit_price), COST)
            amount = quantize(quantity * unit_price, MONEY) if inbound is not False else Decimal("0")
            prepared.append(
                dict(
                    line_no=index,
                    product_id=product.id,
                    unit_id=item.unit_id,
                    unit_to_base_rate=Decimal(unit["to_base_rate"]),
                    quantity=quantity,
                    base_quantity=base_quantity,
                    unit_price=unit_price,
                    amount=amount,
                    batch_no=batch_no,
                    production_date=item.production_date if product.batch_enabled else None,
                    expiry_date=item.expiry_date if product.batch_enabled else None,
                    serial_numbers=json.dumps(serials, ensure_ascii=False) if serials else None,
                    remark=item.remark,
                )
            )
        return prepared

    async def operation_detail(self, header_model, line_model, foreign_key: str, document_id: int):
        """读取库存作业表头、明细和商品展示信息。"""

        header = await self.db.get(header_model, document_id)
        if header is None or header.is_delete:
            raise CustomException("库存作业单据不存在")
        await self.db.refresh(header)
        lines = list(
            (await self.db.scalars(select(line_model).where(getattr(line_model, foreign_key) == document_id).order_by(line_model.line_no))).all()
        )
        products = {
            product.id: product
            for product in (await self.db.scalars(select(master_models.ErpProduct).where(master_models.ErpProduct.id.in_({x.product_id for x in lines} or {0})))).all()
        }
        result = {key: getattr(header, key) for key in header.get_column_attrs()}
        result["lines"] = []
        for line in lines:
            await self.db.refresh(line)
            row = {key: getattr(line, key) for key in line.get_column_attrs()}
            for field in ("serial_numbers", "system_serial_numbers", "counted_serial_numbers"):
                if field in row:
                    row[field] = json.loads(row[field]) if row[field] else []
            product = products.get(line.product_id)
            if product:
                row["product"] = {
                    **sku_snapshot(product), "batch_enabled": product.batch_enabled,
                    "serial_enabled": product.serial_enabled, "base_unit_id": product.base_unit_id,
                    "units": await self.catalog.product_units(product),
                }
            result["lines"].append(row)
        return jsonable_encoder(result)

    async def list_documents(self, model, date_field, number_field, page: int, limit: int, status=None, keyword=None):
        """统一分页读取库存作业单据。"""

        conditions = [model.is_delete == false()]
        if status:
            conditions.append(model.status == status)
        if keyword:
            conditions.append(getattr(model, number_field).like(f"%{keyword.strip()}%"))
        total = await self.db.scalar(select(func.count(model.id)).where(*conditions))
        rows = list((await self.db.scalars(select(model).where(*conditions).order_by(getattr(model, date_field).desc(), model.id.desc()).offset((max(page, 1) - 1) * limit).limit(limit))).all())
        return jsonable_encoder([{key: getattr(row, key) for key in row.get_column_attrs()} for row in rows]), total or 0
