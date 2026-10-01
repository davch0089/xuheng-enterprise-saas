# StockPostingEngine 调用规范

`StockPostingEngine` 是唯一允许修改库存余额、批次库存、序列号状态和库存流水的应用服务。业务模块不得直接更新这些表。模块拆分说明参见 [ARCHITECTURE.md](./ARCHITECTURE.md)。

库存成本已经由独立的 `InventoryCostEngine` 管理，普通出入库仍只调用本引擎，成本会在同一事务中自动联动。成本调整和重新计价参见 [COSTING.md](./COSTING.md)。

## 基本调用流程

业务单据审核必须在同一个数据库事务中完成：

1. 使用 `SELECT ... FOR UPDATE` 锁定业务单据。
2. 检查单据是否为待审核状态。
3. 将每条业务明细转换成 `StockMovement`。
4. 调用 `StockPostingEngine.post()`。
5. 更新业务单据的审核状态和 `posting_version`。
6. 事务提交；任意步骤异常则整体回滚。

FastAPI 当前使用的 `db_getter` 已经为一次请求提供事务边界，因此业务服务只需要复用 `auth.db`，不要自行提交事务。

## 收入类业务示例

```python
from datetime import datetime
from decimal import Decimal

from apps.erp.inventory.posting import (
    MovementType,
    PostingRequest,
    StockMovement,
    StockPostingEngine,
)

movements = tuple(
    StockMovement(
        movement_type=MovementType.PURCHASE_IN,
        business_line_id=line.id,
        movement_role="purchase_in",
        product_id=line.product_id,
        warehouse_id=line.warehouse_id,
        quantity=Decimal(line.base_quantity),
        amount=Decimal(line.amount),
        batch_no=line.batch_no,
        production_date=line.production_date,
        expiry_date=line.expiry_date,
        serial_numbers=tuple(line.serial_numbers),
    )
    for line in lines
)

await StockPostingEngine(db).post(
    PostingRequest(
        source_type="purchase_receipt",
        source_id=receipt.id,
        source_no=receipt.receipt_no,
        posting_version=receipt.posting_version + 1,
        movements=movements,
        occurred_at=datetime.now(),
        operator_id=user_id,
    )
)
```

收入类移动必须提供总成本 `amount`，或者提供主单位成本 `unit_cost`。引擎负责计算移动平均成本。

## 发出类业务示例

```python
movement = StockMovement(
    movement_type=MovementType.SALE_OUT,
    business_line_id=line.id,
    movement_role="sale_out",
    product_id=line.product_id,
    warehouse_id=line.warehouse_id,
    quantity=Decimal(line.base_quantity),
    batch_no=line.batch_no,
    serial_numbers=tuple(line.serial_numbers),
)

await StockPostingEngine(db).post(
    PostingRequest(
        source_type="sale_delivery",
        source_id=delivery.id,
        source_no=delivery.delivery_no,
        posting_version=delivery.posting_version + 1,
        movements=(movement,),
        operator_id=user_id,
    )
)
```

发出类业务不传成本。引擎自动使用过账时的移动平均成本，并校验可用库存、批次库存和序列号状态。

## 调拨示例

同一调拨明细创建一出一入两条移动，业务行 ID 相同、角色不同。调出必须排在调入之前，引擎会自动把调出成本传递给调入移动。

```python
movements = (
    StockMovement(
        movement_type=MovementType.TRANSFER_OUT,
        business_line_id=line.id,
        movement_role="transfer_out",
        product_id=line.product_id,
        warehouse_id=document.source_warehouse_id,
        quantity=Decimal(line.base_quantity),
        batch_no=line.batch_no,
        serial_numbers=tuple(line.serial_numbers),
    ),
    StockMovement(
        movement_type=MovementType.TRANSFER_IN,
        business_line_id=line.id,
        movement_role="transfer_in",
        product_id=line.product_id,
        warehouse_id=document.target_warehouse_id,
        quantity=Decimal(line.base_quantity),
        batch_no=line.batch_no,
        serial_numbers=tuple(line.serial_numbers),
    ),
)
```

## 冲销示例

反审核不允许删除原流水，必须调用冲销：

```python
await StockPostingEngine(db).reverse(
    source_type="sale_delivery",
    source_id=delivery.id,
    posting_version=delivery.posting_version,
    source_no=delivery.delivery_no,
    operator_id=user_id,
)
```

引擎会写入方向相反的新流水，并恢复余额、批次和序列号状态。如果存在未冲销的后续业务，引擎会拒绝当前冲销。

## 幂等规则

幂等键由引擎生成：

```text
POST:{source_type}:{source_id}:V{posting_version}:L{business_line_id}:{movement_role}
```

同一个请求重复调用不会重复扣减或增加库存，而是返回第一次生成的流水。重新审核已经冲销的单据时必须增加 `posting_version`。

## 禁止事项

- 禁止直接更新 `erp_inventory_balance`。
- 禁止直接更新批次数量或序列号状态。
- 禁止修改或删除 `erp_inventory_ledger`；更正只能生成冲销流水。
- 禁止在库存过账成功后单独提交业务单据状态，两者必须在同一事务中完成。
