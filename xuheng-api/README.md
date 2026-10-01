# 序衡 API

FastAPI 后端，包含商品、订单、用户权限、库存资金、数据库迁移和开放接口。作品集对照见仓库根目录 `docs/portfolio.md`。

完整安装步骤见仓库根目录的 `docs/installation.md`，环境变量说明见 `.env.example`。

常用命令：

```bash
# 首次初始化空数据库
python main.py init --env dev

# 启动接口
python main.py run

# 将已有数据库升级到最新迁移
python main.py migrate --env dev

# 仅开发者生成迁移
python main.py revision "change description" --env dev
```

主要领域位于 `apps/erp`：`master`、`purchase`、`sales`、`inventory`、`finance` 和 `documents`。
