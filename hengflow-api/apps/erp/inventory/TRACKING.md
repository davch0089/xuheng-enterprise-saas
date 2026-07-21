# 批次与序列号

批次、效期和序列号仍由 `StockPostingEngine` 统一维护，业务模块不得直接修改对应余额或状态表。

## 批次与效期

- 商品启用 `batch_enabled` 后，每次库存移动必须携带 `batch_no`。
- 入库移动可以同时写入 `production_date`、`expiry_date`；批次余额会保留效期。
- `GET /erp/inventory/batch-allocation` 接收 `warehouse_id`、`product_id`、`quantity`，按“先到期先出（FEFO），再先进先出（FIFO）”返回建议批次、建议数量和库存缺口。
- 已过期批次仍会显示，但返回 `expired=true`。是否允许过期品出库由业务质量制度决定，库存引擎不擅自替业务作废库存。

批次推荐只提供决策建议，不会绕过业务单据自动扣库。调用方应将用户确认的批次写入 `StockMovement.batch_no`。

## 序列号生命周期

`erp_inventory_serial` 保存序列号当前状态；`erp_inventory_serial_movement` 保存不可变的历史事件。每次入库、出库、调拨、组装、拆卸和冲销都会记录：

- 来源单据与库存移动类型；
- 变动前后状态；
- 变动前后仓库；
- 变动前后批次；
- 发生时间与操作人。

在库序列号的 `warehouse_id` 指向当前仓库；已出库或已冲销序列号没有当前库位，`warehouse_id` 为 `NULL`。冲销会依据原生命周期事件精确恢复上一状态、仓库和批次。

使用 `GET /erp/inventory/stock-serials/{serial_id}/history` 查询完整履历。升级前已存在的序列号不会伪造历史；它们从升级后的下一次真实移动开始记录规范化事件。

业务过账示例仍使用标准移动对象：

```python
movement = StockMovement(
    movement_type=MovementType.SALE_OUT,
    business_line_id=line.id,
    movement_role="sale_out",
    product_id=line.product_id,
    warehouse_id=line.warehouse_id,
    quantity=line.base_quantity,
    batch_no=line.batch_no,
    serial_numbers=tuple(line.serial_numbers),
)
```

无需单独调用序列号服务；`StockPostingEngine.post()` 和 `reverse()` 会在同一事务内同步当前状态和生命周期流水。
