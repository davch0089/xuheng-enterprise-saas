"""ERP 事务冒烟脚本共用的轻量数据工厂。"""


async def create_product(session, models, *, code, name, category_id, base_unit_id, **kwargs):
    """创建一个带独立 SPU 的默认 SKU，供非持久化回归脚本使用。"""

    spu = models.ErpProductSpu(
        code=code,
        name=name,
        category_id=category_id,
        brand=kwargs.get("brand"),
    )
    session.add(spu)
    await session.flush()
    product = models.ErpProduct(
        spu_id=spu.id,
        code=code,
        name=name,
        category_id=category_id,
        base_unit_id=base_unit_id,
        variant_name="默认规格",
        variant_key="__DEFAULT__",
        is_default_sku=True,
        **kwargs,
    )
    session.add(product)
    await session.flush()
    return product
