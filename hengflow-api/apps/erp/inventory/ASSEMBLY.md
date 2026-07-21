# 组装与拆卸

## BOM 模型

简化 BOM 由成品、标准产出数量、版本和若干子件组成。每个子件记录单位、标准用量和损耗率。保存时会校验商品单位并固化相对主单位换算率，同时禁止成品引用自身和重复子件。

接口：

- `GET/POST /erp/inventory/boms`
- `GET/PUT /erp/inventory/boms/{id}`
- `DELETE /erp/inventory/boms`

已被工单引用的 BOM 不可删除。工单保存时会展开 BOM 并固化行快照，因此后续修改 BOM 不会改变历史工单。

## 组装

审核组装工单时，在同一数据库事务内依次完成：

1. 按工单数量展开 BOM，子件用量包含损耗率。
2. 子件以 `MATERIAL_OUT` 出库，由永续移动平均成本引擎计算实际发出成本。
3. 汇总所有子件的实际发出成本。
4. 成品以 `PRODUCTION_IN` 入库，入库总成本等于归集的子件成本。
5. 保存工单行实际成本、审核人、审核时间和过账版本。

## 拆卸

审核拆卸工单时：

1. 成品以 `MATERIAL_OUT` 出库，取得实际发出成本。
2. 优先按各子件“当前移动平均成本 × 回收数量”的权重分摊；没有有效成本权重时按数量分摊。
3. 尾差归入最后一个子件，保证分摊金额严格等于成品发出成本。
4. 子件以 `PRODUCTION_IN` 入库并更新各自移动平均成本。

## 冲销与调用

接口：

- `GET/POST /erp/inventory/assembly-orders`
- `GET/PUT /erp/inventory/assembly-orders/{id}`
- `DELETE /erp/inventory/assembly-orders`
- `POST /erp/inventory/assembly-orders/{id}/approve`
- `POST /erp/inventory/assembly-orders/{id}/unapprove`

应用内可直接复用服务：

```python
from apps.erp.inventory.services.assembly import AssemblyOrderService, BomService

bom = await BomService(db, user_id).save(bom_input)
order = await AssemblyOrderService(db, user_id).save(order_input)
posted = await AssemblyOrderService(db, user_id).approve(order["id"])
```

反审核会按入库后出库的逆序调用 `StockPostingEngine.reverse()`，同时冲销数量、批次、序列号、成本余额和不可变流水。若成品已经被后续业务消耗而无法冲销，操作会失败并整体回滚。
