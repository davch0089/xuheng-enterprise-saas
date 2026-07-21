"""简化BOM维护服务。"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete, false, func, select

from apps.erp.common import QTY, quantize
from apps.erp.master import models as master_models
from apps.erp.master.product_display import sku_snapshot
from core.exception import CustomException

from ... import models
from ...assembly_schemas import BomInput
from ..operations.common import InventoryOperationSupport


class BomService(InventoryOperationSupport):
    """管理BOM版本、成品单位和子件用量。"""

    async def save(self, data: BomInput, bom_id: int | None = None):
        """新增或修改BOM；已经保存的工单行快照不会被同步改写。"""

        finished = await self.active(master_models.ErpProduct, data.product_id, "成品")
        finished_units = {x["unit_id"]: x for x in await self.catalog.product_units(finished)}
        if data.unit_id not in finished_units:
            raise CustomException("BOM产出单位不属于成品")
        prepared = []
        for index, line in enumerate(data.lines, 1):
            product = await self.active(master_models.ErpProduct, line.component_product_id, f"第{index}行子件")
            units = {x["unit_id"]: x for x in await self.catalog.product_units(product)}
            unit = units.get(line.unit_id)
            if unit is None:
                raise CustomException(f"第{index}行单位不属于子件")
            prepared.append(dict(
                line_no=index, component_product_id=product.id, unit_id=line.unit_id,
                unit_to_base_rate=Decimal(unit["to_base_rate"]), quantity=quantize(Decimal(line.quantity), QTY),
                base_quantity=quantize(Decimal(line.quantity) * Decimal(unit["to_base_rate"]), QTY),
                loss_rate=Decimal(line.loss_rate), remark=line.remark,
            ))
        duplicate = await self.db.scalar(select(models.ErpBillOfMaterial.id).where(
            ((models.ErpBillOfMaterial.code == data.code) | ((models.ErpBillOfMaterial.product_id == data.product_id) & (models.ErpBillOfMaterial.version == data.version))),
            models.ErpBillOfMaterial.id != (bom_id or 0),
        ))
        if duplicate:
            raise CustomException("BOM编码或成品版本已存在")
        if bom_id:
            bom = await self.db.get(models.ErpBillOfMaterial, bom_id)
            if bom is None or bom.is_delete:
                raise CustomException("BOM不存在")
            await self.db.execute(delete(models.ErpBillOfMaterialLine).where(models.ErpBillOfMaterialLine.bom_id == bom_id))
        else:
            bom = models.ErpBillOfMaterial()
            self.db.add(bom)
        for field in ("code", "name", "product_id", "unit_id", "output_quantity", "version", "is_active", "remark"):
            setattr(bom, field, getattr(data, field))
        await self.db.flush()
        for item in prepared:
            self.db.add(models.ErpBillOfMaterialLine(bom_id=bom.id, **item))
        await self.db.flush()
        return await self.detail(bom.id)

    async def detail(self, bom_id: int):
        """返回BOM及成品、子件展示信息。"""

        bom = await self.db.get(models.ErpBillOfMaterial, bom_id)
        if bom is None or bom.is_delete:
            raise CustomException("BOM不存在")
        await self.db.refresh(bom)
        lines = list((await self.db.scalars(select(models.ErpBillOfMaterialLine).where(models.ErpBillOfMaterialLine.bom_id == bom_id).order_by(models.ErpBillOfMaterialLine.line_no))).all())
        product_ids = {bom.product_id} | {x.component_product_id for x in lines}
        products = {x.id: x for x in (await self.db.scalars(select(master_models.ErpProduct).where(master_models.ErpProduct.id.in_(product_ids)))).all()}
        result = {key: getattr(bom, key) for key in bom.get_column_attrs()}
        finished = products.get(bom.product_id)
        result["product_name"] = finished.name if finished else None
        result["product_code"] = finished.code if finished else None
        result["product_barcode"] = finished.barcode if finished else None
        result["product_variant_name"] = finished.variant_name if finished else None
        result["product_specification"] = finished.specification if finished else None
        if finished:
            result["finished_product"] = {
                **sku_snapshot(finished),
                "base_unit_id": finished.base_unit_id,
                "batch_enabled": finished.batch_enabled,
                "serial_enabled": finished.serial_enabled,
                "units": await self.catalog.product_units(finished),
            }
        result["lines"] = []
        for line in lines:
            await self.db.refresh(line)
            row = {key: getattr(line, key) for key in line.get_column_attrs()}
            product = products.get(line.component_product_id)
            row["product_code"] = product.code if product else None
            row["product_name"] = product.name if product else None
            row["product_barcode"] = product.barcode if product else None
            row["product_variant_name"] = product.variant_name if product else None
            row["product_specification"] = product.specification if product else None
            if product:
                row["product"] = {
                    **sku_snapshot(product),
                    "base_unit_id": product.base_unit_id,
                    "batch_enabled": product.batch_enabled,
                    "serial_enabled": product.serial_enabled,
                    "units": await self.catalog.product_units(product),
                }
            result["lines"].append(row)
        from fastapi.encoders import jsonable_encoder
        return jsonable_encoder(result)

    async def list(self, page: int, limit: int, keyword=None, is_active=None):
        """分页查询BOM。"""

        conditions = [models.ErpBillOfMaterial.is_delete == false()]
        if keyword:
            conditions.append((models.ErpBillOfMaterial.code.like(f"%{keyword}%")) | (models.ErpBillOfMaterial.name.like(f"%{keyword}%")))
        if is_active is not None:
            conditions.append(models.ErpBillOfMaterial.is_active == is_active)
        total = await self.db.scalar(select(func.count(models.ErpBillOfMaterial.id)).where(*conditions))
        rows = list((await self.db.scalars(select(models.ErpBillOfMaterial).where(*conditions).order_by(models.ErpBillOfMaterial.code).offset((page - 1) * limit).limit(limit))).all())
        product_ids = {x.product_id for x in rows}
        products = {x.id: x for x in (await self.db.scalars(select(master_models.ErpProduct).where(master_models.ErpProduct.id.in_(product_ids or {0})))).all()}
        from fastapi.encoders import jsonable_encoder
        return jsonable_encoder([{
            **{k: getattr(x, k) for k in x.get_column_attrs()},
            "product_code": products.get(x.product_id).code if products.get(x.product_id) else None,
            "product_name": products.get(x.product_id).name if products.get(x.product_id) else None,
            "product_barcode": products.get(x.product_id).barcode if products.get(x.product_id) else None,
            "product_variant_name": products.get(x.product_id).variant_name if products.get(x.product_id) else None,
            "product_specification": products.get(x.product_id).specification if products.get(x.product_id) else None,
        } for x in rows]), total or 0

    async def delete(self, ids: list[int]):
        """删除未被工单引用的BOM。"""

        referenced = await self.db.scalar(select(models.ErpAssemblyOrder.id).where(models.ErpAssemblyOrder.bom_id.in_(ids)).limit(1))
        if referenced:
            raise CustomException("BOM已被组装拆卸工单引用，不能删除")
        await self.db.execute(delete(models.ErpBillOfMaterialLine).where(models.ErpBillOfMaterialLine.bom_id.in_(ids)))
        await self.db.execute(delete(models.ErpBillOfMaterial).where(models.ErpBillOfMaterial.id.in_(ids)))
