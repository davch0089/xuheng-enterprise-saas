# ERP 资金、核销、期间与经营利润

## 功能边界

本模块负责资金账户余额、不可变资金流水、核销、会计期间和经营利润查询。应收、应付及库存成本仍由各自领域服务维护，财务服务通过业务单据编号和版本号与它们联动。

## 资金业务

- `receipt`：一般收款，审核后增加收款账户余额。
- `payment`：一般付款，审核后减少付款账户余额。
- `transfer`：账户转账，在同一事务内生成转出、转入两条流水。
- 销售收款与采购付款审核时也必须选择资金账户，并分别写入收款、付款流水。
- 已审核单据不允许直接修改或删除。反审核会追加金额相反的冲销流水，不修改历史流水；再次审核会增加 `posting_version`，保证幂等。

资金接口位于 `/erp/finance/accounts`、`/erp/finance/documents` 和 `/erp/finance/ledgers`。

## 五类核销

1. 客户收款核销应收：在销售收款单中选择应收项目。
2. 供应商付款核销应付：在采购付款单中选择应付项目。
3. `advance_receipt_ar`：以前期客户收款形成的预收冲销应收。
4. `advance_payment_ap`：以前期供应商付款形成的预付冲销应付。
5. `ar_ap_offset`：同额应收、应付对冲，双方明细金额必须分别等于核销单总额。

核销单采用“草稿 → 审核 → 已冲销”状态流转。反审核按原分配逐项恢复应收、应付未核销金额，并为对冲产生反向台账，禁止物理改写已审核结果。接口位于 `/erp/finance/open-items` 和 `/erp/finance/settlements`。

## 会计期间

- 系统尚未建立任何会计期间时保持兼容模式，不限制业务日期。
- 建立首个期间后即启用期间控制；业务日期必须落在一个已启用且状态为 `open` 的期间内。
- 保存、审核、反审核和冲销均检查原业务日期，已结账期间禁止跨期修改。
- 结账前检查期间内未完成草稿、库存数量与成本余额数量、待重新计价成本以及尚未冲回的暂估负库存成本。
- 只能从时间上最新的已结账期间开始反结账，避免破坏期间顺序。

接口位于 `/erp/finance/periods`；`GET /erp/finance/periods/cost-validation/{end_date}` 可单独执行成本期末校验。

## 经营利润口径

报表只统计查询区间内已审核业务：

```text
销售净收入 = 销售出库收入 - 销售退货冲回收入
销售成本   = 销售出库成本 - 销售退货冲回成本
毛利       = 销售净收入 - 销售成本
贡献利润   = 毛利 - 变动费用
毛利率     = 毛利 / 销售净收入 × 100%
```

变动费用来自已审核的一般付款单，且 `profit_category` 为 `variable_expense`。报表同时返回 SKU 维度的销售净收入、销售成本和毛利明细。接口为 `GET /erp/finance/profit?date_start=YYYY-MM-DD&date_end=YYYY-MM-DD`。

## 服务层调用

业务代码应复用服务层，并与业务单据处于同一个数据库事务：

```python
from apps.erp.finance.services import (
    AccountingPeriodService,
    FundDocumentService,
    ProfitQueryService,
    SettlementService,
)

await AccountingPeriodService(db, user_id).ensure_open(business_date, "审核单据")
document = await FundDocumentService(db, user_id).approve(document_id)
settlement = await SettlementService(db, user_id).approve(settlement_id)
report = await ProfitQueryService(db).report(date_start, date_end)
```

服务方法只执行 `flush`，事务提交或回滚由 API 的统一数据库依赖负责。
