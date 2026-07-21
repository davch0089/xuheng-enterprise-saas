# InventoryCostEngine 调用规范

`InventoryCostEngine` 是库存成本的唯一写入口，负责永续移动平均、成本余额、出库成本、成本调整、重新计价、幂等和不可变成本流水。

## 普通出入库怎么调用

采购入库、销售出库、调拨、盘盈盘亏等数量业务**不要直接调用成本引擎**，仍然调用 `StockPostingEngine`：

```python
await StockPostingEngine(db).post(
    PostingRequest(
        source_type="sale_delivery",
        source_id=document.id,
        source_no=document.document_no,
        posting_version=document.posting_version + 1,
        movements=movements,
        operator_id=user_id,
    )
)
```

库存引擎会在同一个数据库事务中自动调用成本引擎：

- 收入：按 `amount` 或 `unit_cost` 更新移动平均成本。
- 发出：自动取过账时的移动平均成本，生成出库成本。
- 调拨：自动把调出成本传递给调入仓库。
- 冲销：同时冲销库存流水和对应成本流水，恢复原余额。
- 重复请求：库存和成本都通过幂等键返回第一次的结果，不重复记账。

业务服务不得自己更新 `erp_inventory_cost_balance`、`erp_inventory_cost_ledger`，也不要在调用引擎后单独提交事务。

## 成本调整

成本调整只改库存价值，不改数量。例如将一笔运费、关税或盘点差额分摊到某仓库商品：

```python
from decimal import Decimal

from apps.erp.inventory.costing import (
    CostAdjustmentRequest,
    InventoryCostEngine,
)

result = await InventoryCostEngine(db).adjust(
    CostAdjustmentRequest(
        idempotency_key=f"COST_ADJUST:{document.id}:V{document.posting_version + 1}",
        cost_no=f"{document.document_no}-V{document.posting_version + 1}",
        source_type="cost_adjustment",
        source_id=document.id,
        source_no=document.document_no,
        posting_version=document.posting_version + 1,
        warehouse_id=line.warehouse_id,
        product_id=line.product_id,
        amount=Decimal(line.adjustment_amount),  # 增值为正，减值为负
        source_line_id=line.id,
        operator_id=user_id,
        remark=line.remark,
    )
)
```

`result.ledger.id` 是成本流水 ID；`result.average_cost_after` 和 `result.value_after` 是调整后的平均成本和库存价值。

## 重新计价

重新计价指定新的主单位平均成本，引擎自动计算应调整的库存价值差额：

```python
from apps.erp.inventory.costing import (
    CostRevaluationRequest,
    InventoryCostEngine,
)

result = await InventoryCostEngine(db).revalue(
    CostRevaluationRequest(
        idempotency_key=f"REVALUE:{document.id}:V{document.posting_version + 1}",
        cost_no=f"{document.document_no}-V{document.posting_version + 1}",
        source_type="cost_revaluation",
        source_id=document.id,
        source_no=document.document_no,
        posting_version=document.posting_version + 1,
        warehouse_id=line.warehouse_id,
        product_id=line.product_id,
        target_average_cost=Decimal(line.target_average_cost),
        source_line_id=line.id,
        operator_id=user_id,
        remark=line.remark,
    )
)
```

重新计价会生成 `REVALUATION` 成本流水，不会覆盖历史流水。零库存重新计价会把残留库存价值清零。

## 冲销成本调整或重新计价

```python
await InventoryCostEngine(db).reverse_value_change(
    original_cost_ledger_id=result.ledger.id,
    source_type="cost_revaluation",
    source_id=document.id,
    source_no=document.document_no,
    posting_version=document.posting_version,
    operator_id=user_id,
)
```

冲销必须按业务发生的倒序执行；如果存在未冲销的后续成本业务，引擎会拒绝冲销，避免破坏移动平均成本链。

## 事务和幂等规则

- 锁定业务单据、调用引擎、修改单据状态必须处于同一个事务。
- `idempotency_key` 必须稳定且唯一，建议包含单据类型、ID、版本和行 ID。
- 已冲销单据重新审核时必须增加 `posting_version`，不能复用原版本。
- 成本流水不可更新、不可删除；更正只能通过冲销、成本调整或重新计价。
- 仓库允许负库存时，发出成本会按当时平均成本暂估并标记 `provisional`；成本余额的 `needs_revaluation` 会提示后续执行重新计价。

## 核心数据表

- `erp_inventory_cost_balance`：仓库 + 商品维度的数量、库存价值和移动平均成本。
- `erp_inventory_cost_ledger`：每次成本变动的不可变流水，并关联对应的 `erp_inventory_ledger`。
- `erp_inventory_balance.average_cost/inventory_value`：为库存查询保留的成本镜像，由成本引擎同步，业务模块不能直接修改。
