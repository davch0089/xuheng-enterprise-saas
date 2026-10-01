# ERP 文档中心

该领域提供三项可复用能力：Excel 数据导入导出、HTML 打印模板和业务附件。

## 数据导入导出

- 菜单：`ERP / 文档与工具 / 数据导入导出`
- 当前资源：商品分类、计量单位、仓库、客户、供应商、职员、结算方式。
- 导入只接受 `.xlsx`，以“编码”为业务唯一键。
- `upsert` 会新增资料并覆盖同编码记录，`create` 只允许新增。
- 每行使用独立保存点，某一行失败不会回滚其他正确行；错误会记录到任务历史。
- 新资源在 `services/exchange.py` 的 `RESOURCES` 中注册字段、模型和 Pydantic Schema 即可复用整个流程。

## 打印模板

- 菜单：`ERP / 文档与工具 / 打印模板`
- 模板由 HTML、CSS、纸张参数和示例 JSON 组成。
- 支持 `{{ field }}` 变量和 `{% for line in lines %}` 明细循环。
- 渲染在 Jinja2 沙箱中执行，未提供的字段会直接提示模板错误。
- 业务页面调用 `POST /erp/documents/print-templates/render`，传入 `template_id`（或 `business_type`）和单据数据即可获得完整打印 HTML。

示例：

```json
{
  "business_type": "purchase_receipt",
  "data": {
    "document_no": "RK202607200001",
    "lines": []
  }
}
```

同一业务类型只允许一个默认模板。业务单据页面以后只需传 `business_type`，即可使用当前默认模板，无需写死模板 ID。

采购、销售单据列表和详情中已经提供打印入口，使用以下业务类型：

- `purchase_order`、`purchase_receipt`、`purchase_return`
- `sales_order`、`sales_delivery`、`sales_return`

尚未配置对应业务默认模板时会自动使用 `generic` 通用模板；新增同业务类型的默认模板后，打印入口会自动切换，无需修改页面代码。

## 业务附件

- 菜单：`ERP / 文档与工具 / 附件管理`
- 通过 `business_type + business_id` 关联任意业务对象，不需要修改原业务表。
- 上传、查询、下载和删除接口均位于 `/erp/documents/attachments`。
- 单个附件最大 50 MB，扩展名白名单见 `services/storage.py`。
- 本地文件保存在 `static/erp/attachments`；删除附件会同时删除物理文件。

推荐业务类型：

| 单据 | business_type |
| --- | --- |
| 采购订单 | `purchase_order` |
| 采购入库 | `purchase_receipt` |
| 销售订单 | `sales_order` |
| 销售出库 | `sales_delivery` |
| 盘点单 | `inventory_count` |

## OSS 配置

上传时可以选择 `local` 或 `oss`。使用 OSS 前，在当前运行环境的 `application/config/*.py` 配置：

```python
ALIYUN_OSS = {
    "accessKeyId": "RAM AccessKey ID",
    "accessKeySecret": "RAM AccessKey Secret",
    "endpoint": "https://oss-cn-hangzhou.aliyuncs.com",
    "bucket": "bucket-name",
    "baseUrl": "https://bucket-name.oss-cn-hangzhou.aliyuncs.com/",
}
```

建议使用权限最小化的 RAM 用户。私有 Bucket 下载时由后端生成一小时有效的签名地址。
