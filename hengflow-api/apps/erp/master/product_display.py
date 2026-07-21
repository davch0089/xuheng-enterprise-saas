"""ERP 各业务模块共用的 SKU 展示快照。"""


def sku_snapshot(product) -> dict:
    """返回可安全固化到单据查询结果中的 SKU 识别字段。"""

    return {
        "id": product.id,
        "spu_id": product.spu_id,
        "code": product.code,
        "name": product.name,
        "barcode": product.barcode,
        "variant_name": product.variant_name,
        "specification": product.specification,
    }


def sku_display_spec(product) -> str:
    """组合规格维度名称和规格型号，过滤重复值及默认规格占位。"""

    values = []
    for value in (product.variant_name, product.specification):
        normalized = str(value or "").strip()
        if normalized and normalized != "默认规格" and normalized not in values:
            values.append(normalized)
    return " / ".join(values) or "默认规格"


def sku_label(product) -> str:
    """生成后端日志或导出可用的 SKU 完整名称。"""

    return f"{product.code} {product.name} / {sku_display_spec(product)}"
