# 商品 SPU / SKU 设计与调用约定

## 核心约定

- `erp_product_spu` 是商品公共档案，不参与库存过账。
- `erp_product` 是 SKU；其 `id` 继续作为采购、销售、库存、成本、批次、序列号和 BOM 中的 `product_id`。
- `erp_product.code` 和非空 `barcode` 全局唯一。
- 库存及成本继续按 `warehouse_id + product_id` 独立核算，不新增重复的 `sku_id`。

## 业务展示规范

- `erp_product.id` 就是所有采购、销售、出入库、库存和成本明细中的 SKU 标识，业务表中的 `product_id` 均指向 SKU，而不是 SPU。
- 商品选择器统一显示“SKU编码 + 商品名称 + 规格组合/规格型号 + 条码”，不能只显示商品名称。
- 单据详情和来源单据返回 `product` SKU 快照，至少包含 `code`、`name`、`barcode`、`variant_name` 和 `specification`。
- 库存余额、流水、批次、序列号和利润统计使用独立的“SKU编码”“SKU规格”列；库存与成本仍按每个 SKU 独立汇总。
- 前端统一使用 `src/utils/erp/product.ts` 的 `skuLabel` 和 `skuSpec`，避免各页面产生不同展示口径。
- 单纯包装计量差异使用 SKU 的多单位方案；需要独立条码、库存或价格时才新建 SKU。

## 商品维护接口

```text
GET    /erp/master/product-spus
GET    /erp/master/product-spus/{id}
POST   /erp/master/product-spus
PUT    /erp/master/product-spus/{id}
DELETE /erp/master/product-spus/{id}
GET    /erp/master/product-spus/attribute-options
```

新增或修改时一次提交 SPU 和全部 SKU：

```json
{
  "code": "TSHIRT",
  "name": "运动T恤",
  "category_id": 1,
  "brand": "示例品牌",
  "is_active": true,
  "skus": [
    {
      "code": "TSHIRT-RED-M",
      "barcode": "690000000001",
      "base_unit_id": 1,
      "is_default_sku": true,
      "attributes": [
        {"name": "颜色", "value": "红色"},
        {"name": "尺寸", "value": "M"}
      ]
    }
  ]
}
```

## 业务模块调用

商品搜索接口返回的 `id` 是 SKU ID。采购、销售、库存等业务单据保持原调用方式：

```json
{
  "product_id": 123,
  "unit_id": 1,
  "quantity": 10
}
```

条码扫描直接匹配 SKU 条码；使用 SPU 编码或名称搜索时会返回其全部启用 SKU。

已有库存流水后，SKU 的单位、多单位方案、成本方式、批次和序列号设置不可修改。已被业务引用的 SKU 不允许删除，只能停用，以保证历史单据和不可变流水连续。
