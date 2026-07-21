# 销售管理流程

销售模块实现从销售订单到客户回款的完整 Order-to-Cash 流程，并复用库存模块的 `StockPostingEngine` 和 `CostingEngine`。单据服务只负责业务状态，库存数量、库存流水和成本流水仍由独立引擎维护。

## 业务流程

```text
销售订单草稿
  └─审核 → 预占库存 → 已审核
                 └─部分/全部出库 → 部分履约/已完成

销售出库草稿（可以引用订单，也可以直接出库）
  └─审核 → 释放本次订单预占 → SALE_OUT 库存过账
       → 永续移动平均成本结转 → 生成客户应收 → 记录毛利

销售退货草稿（必须引用已审核销售出库）
  └─审核 → 按原出库成本 SALE_RETURN 回库 → 冲减客户应收

销售收款草稿
  └─审核 → 按指定明细核销；未指定时按到期日 FIFO 自动核销应收
```

所有审核操作都在同一个数据库事务内完成。任何一个环节失败，单据、库存、成本和应收会一起回滚。

## 关键规则

- 订单审核只预占可用库存，不产生库存流水、成本或应收。
- 销售出库允许有订单出库和无订单直接出库；引用订单时不能超出订单未履约数量。
- 出库批次支持 `batch_selection_mode=auto|manual`。自动模式跳过过期批次，按最早效期优先、再按生产日期和批次记录顺序分配；数量跨批次时服务会自动拆行。
- 序列号商品仍需选择具体序列号；自动模式会按序列号当前所在批次归组，无需重复填写批次号。
- 审核出库使用 `MovementType.SALE_OUT`，库存不足、批次不匹配或序列号不合法时整体失败。
- 退货必须引用原出库明细，不能超过可退数量，退货成本沿用原出库单位成本，避免当前平均成本造成毛利漂移。
- 应收余额、应收开放项和不可变应收流水同步维护；业务更正使用冲销流水，不能修改或删除历史流水。
- 已发生退货或收款的出库单不能直接反审核，应先按“收款 → 退货 → 出库 → 订单”的顺序撤销下游单据。
- 单据重复审核会被状态机拒绝；重新审核已经反审核的单据时 `posting_version` 自增，库存与应收幂等键随版本变化。

## 后端调用方式

业务代码应调用领域服务，不应直接修改库存余额、成本余额或应收余额：

```python
from apps.erp.sales.services import (
    SalesDeliveryService,
    SalesOrderService,
    SalesReceiptService,
    SalesReturnService,
)

order_service = SalesOrderService(db, user_id=current_user_id)
order = await order_service.save(order_input)
await order_service.approve(order["id"])

delivery_service = SalesDeliveryService(db, user_id=current_user_id)
delivery = await delivery_service.save(delivery_input)
await delivery_service.approve(delivery["id"])
```

服务方法不会自行提交事务。HTTP 请求依赖统一负责提交/回滚；脚本或其他模块调用时应在外层使用事务：

```python
async with session.begin():
    await SalesReturnService(session, user_id).approve(return_id)
```

## HTTP 接口

- `/erp/sales/orders`：销售订单增删改查、审核、反审核。
- `/erp/sales/deliveries`：销售出库增删改查、审核、反审核。
- `/erp/sales/returns`：销售退货增删改查、审核、反审核。
- `/erp/sales/receivables`：应收开放项查询。
- `/erp/sales/receipts`：收款单增删改查、审核、反审核。
- `/erp/sales/source-orders`：出库可引用的未完成订单。
- `/erp/sales/source-deliveries`：退货可引用且仍有可退数量的出库单。
- `/erp/sales/products`、`/erp/sales/options`：销售表单商品库存和基础资料选项。

## 目录职责

- `entities/`：订单、出库、退货、预占、应收、收款 ORM 实体。
- `schemas/`：HTTP 与领域服务输入模型。
- `services/`：单据状态、库存联动、成本结转、应收与核销业务。
- `queries/`：列表、来源单据和表单选项只读查询。
- `api/`：路由、权限和依赖装配。

数据库结构由迁移 `b39e75dab642_sales_management_flow.py` 创建，同时安装销售菜单和按钮权限。
