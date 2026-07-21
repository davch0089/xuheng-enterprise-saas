# 库存模块目录结构

库存模块按领域职责拆分，入口文件只负责兼容导出或路由聚合，不再承载业务实现。

```text
inventory/
├─ api/                       HTTP 接口
│  ├─ dependencies.py         服务依赖工厂
│  ├─ inbound.py              入库单接口
│  ├─ stock.py                库存、批次和序列号查询接口
│  └─ assembly.py             BOM、组装与拆卸接口
├─ common/                    旧导入路径兼容层
│  └─ precision.py            转发到 apps.erp.common
├─ entities/                  ORM 实体
│  ├─ documents.py            单据和明细
│  ├─ stock.py                库存、批次、序列号、数量流水
│  ├─ cost.py                 成本余额和成本流水
│  └─ assembly.py             BOM、组装拆卸工单及快照
├─ queries/                   只读查询
│  ├─ base.py                 分页和多单位显示
│  ├─ balances.py             库存余额
│  ├─ movements.py            收发流水
│  └─ tracking.py             批次和序列号
├─ services/
│  ├─ inbound/
│  │  ├─ catalog.py           商品搜索、单位换算、明细校验
│  │  ├─ read.py              入库单详情和列表查询
│  │  └─ service.py           入库单保存、审核和反审核
│  ├─ stock/
│  │  ├─ types.py             移动类型和请求对象
│  │  ├─ engine.py            库存过账主流程
│  │  ├─ tracking.py          批次和序列号变动
│  │  └─ reversals.py         库存冲销
│  ├─ assembly/
│  │  ├─ bom.py               简化 BOM 维护与单位校验
│  │  └─ order.py             BOM 展开、双阶段过账和成本归集
│  └─ cost/
│     ├─ types.py             成本请求和结果对象
│     ├─ engine.py            移动平均、调整和重新计价
│     ├─ repository.py        余额锁和幂等读取
│     └─ reversals.py         成本冲销
├─ models.py                  ORM 兼容导出
├─ crud.py                    入库服务兼容导出
├─ query.py                   查询服务兼容导出
├─ posting.py                 库存引擎兼容导出
├─ costing.py                 成本引擎兼容导出
└─ views.py                   路由聚合
```

## 导入约定

跨采购、销售、库存和财务共用的精度规则位于 ERP 根公共包：

```python
from apps.erp.common import COST, MONEY, QTY, quantize
```

现有代码可以继续使用原路径：

```python
from apps.erp.inventory.posting import StockPostingEngine
from apps.erp.inventory.costing import InventoryCostEngine
from apps.erp.inventory.crud import InventoryService
```

新业务建议从明确的功能包导入：

```python
from apps.erp.inventory.services.stock import StockPostingEngine
from apps.erp.inventory.services.cost import InventoryCostEngine
from apps.erp.inventory.services.inbound import InventoryService
from apps.erp.inventory.queries import InventoryQueryService
```

## 维护边界

- `api` 只处理权限、参数和响应，不写业务规则。
- `queries` 只读取数据，不修改库存或成本余额。
- `services.stock` 是库存数量、批次和序列号的唯一写入口。
- `services.cost` 是库存价值和成本流水的唯一写入口。
- `entities` 只定义持久化结构和不可变流水约束。
- 公共类、函数、接口和校验器必须保留 docstring，说明职责或关键约束。

批次、效期、序列号使用说明参见 [TRACKING.md](./TRACKING.md)，组装与拆卸流程参见 [ASSEMBLY.md](./ASSEMBLY.md)。
