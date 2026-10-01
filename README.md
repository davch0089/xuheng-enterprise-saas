# 序衡

序衡是一个企业 SaaS 后台演示，主线是企业、商品、订单和按数量记账的库存。订单从待确认、待发货走到已完成或已关闭；发货减少该企业的库存数量，退货把数量加回。技术栈是 Vue、TypeScript、Python、MySQL 和 Redis。讲解对照见 [作品集说明](docs/portfolio.md)。

仓库里还保留着一套采购、销售、库存成本和资金期间模块。那套模块沿用上游进销存的单据和过账方式，序衡主线不走那套流程。

部署生产环境前，请自行完成业务验收、安全审计和数据备份方案。

## 技术栈

- 后端：Python 3.10、FastAPI、SQLAlchemy 2、Alembic、MySQL、Redis
- 前端：Vue 3、TypeScript、Vite、Element Plus、Pinia

## 目录

```text
xuheng/
├── xuheng-api/       # FastAPI 接口、迁移和初始化数据
├── xuheng-admin/     # Vue 管理端
├── docs/               # 安装、配置和开发文档
├── LICENSE
├── NOTICE
└── README.md
```

## 快速开始

本项目不提供 Docker 部署，需要预先安装 Python 3.10、MySQL 5.6+、Redis 6.0+、Node.js 18+ 和 pnpm 8+。

详细步骤见 [源码安装文档](docs/installation.md)。

后端概览：

```bash
cd xuheng-api
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py init --env dev
python main.py run
```

前端概览：

```bash
cd xuheng-admin
pnpm install --frozen-lockfile
pnpm dev
```

默认访问地址：

- 管理端：http://127.0.0.1:5000
- API：http://127.0.0.1:9000
- API 文档：http://127.0.0.1:9000/docs

首次管理员账号和密码由 `xuheng-api/.env` 中的 `INITIAL_ADMIN_USERNAME`、`INITIAL_ADMIN_PASSWORD` 决定。首次登录后请立即修改密码。

## 升级

拉取代码并备份数据库后执行：

```bash
cd xuheng-api
python main.py migrate --env pro
```

再重新构建并发布前端静态文件。详细说明见 [升级文档](docs/upgrade.md)。

## 开源协议与来源

本仓库衍生自 [HengFlow ERP](https://github.com/liyanzhang516/hengflow-erp)。HengFlow ERP 衍生自 Kinit 和 vue-element-plus-admin。三者都使用 MIT License。

MIT 允许使用、修改和再分发，不把原作者的著作权转给后续修改者。Kinit、vue-element-plus-admin 和 HengFlow ERP 对各自原有代码的著作权仍然有效，声明在 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。序衡新增的企业、订单履约和数量库存是在这个许可证下写的后续改动。

欢迎通过 Issue 报告问题，通过 Pull Request 参与开发。提交前请阅读 [贡献指南](CONTRIBUTING.md) 和 [安全策略](SECURITY.md)。
