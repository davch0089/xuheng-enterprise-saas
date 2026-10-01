# 库存作业流程

库存作业单据只负责业务状态编排，数量、批次、序列号、成本、幂等、行锁和不可变流水统一交给 `StockPostingEngine`。

## 调拨

- 一步调拨：发运时在同一事务内完成源仓 `TRANSFER_OUT` 和目标仓 `TRANSFER_IN`，任一步失败都会整体回滚。
- 两步调拨：发运后状态为 `in_transit`，源仓库存已经扣减；到货确认后才增加目标仓库存。
- 调入金额使用调出流水的实际移动平均成本，不会按目标仓成本重新估价。
- 撤销顺序固定为目标仓收货冲销，再冲销源仓发运；存在后续库存业务时由过账引擎拒绝冲销。

## 盘点与盘盈盘亏

- 生成盘点明细时按商品、批次和序列号取得账面快照。
- 保存盘点单时记录账面数量、实盘数量、差异和快照成本。
- 审核前再次校验当前库存是否仍与快照一致；库存发生变化时必须重新保存盘点单。
- 正差异使用 `STOCK_GAIN`，按快照平均成本入库；负差异使用 `STOCK_LOSS`，按当前移动平均成本出库。
- 无差异盘点允许审核，但不会伪造零数量库存流水。

## 其他出入库

- 其他入库使用 `OTHER_IN`，录入成本参与永续移动平均。
- 其他出库使用 `OTHER_OUT`，出库成本由成本引擎自动结转。
- 审核后不可修改或删除，只能反审核生成冲销流水。

## 状态与接口

- 调拨：`draft -> in_transit -> completed`，接口位于 `/erp/inventory/transfers`。
- 盘点：`draft -> approved`，接口位于 `/erp/inventory/counts`。
- 其他出入库：`draft -> approved`，接口位于 `/erp/inventory/other-orders`。
- 仓库盘点快照：`GET /erp/inventory/count-snapshot?warehouse_id=...`。

迁移 `c7e4a19f2d81_inventory_operations.py` 创建相关表、菜单权限，并为序列号补充批次维度。
