# HengFlow ERP

HengFlow ERP 是一个基于 FastAPI、Vue 3 和 MySQL 的开源进销存与经营管理系统，面向中小企业的采购、销售、库存、资金和经营分析场景。

> 当前处于积极开发阶段。部署生产环境前，请自行完成业务验收、安全审计和数据备份方案。

## 功能

- 基础资料：商品 SPU/SKU、多单位、仓库、客户、供应商、职员
- 采购管理：采购订单、采购入库、采购退货、应付和付款
- 销售管理：销售订单、销售出库、销售退货、应收和收款
- 库存管理：库存过账、成本核算、调拨、盘点、批次和序列号
- 生产作业：简化 BOM、组装与拆卸
- 财务管理：资金账户、收付款、核销、会计期间和经营利润
- 公共能力：Excel 导入导出、打印模板、本地/OSS 附件、操作日志

## 技术栈

- 后端：Python 3.10、FastAPI、SQLAlchemy 2、Alembic、MySQL、Redis
- 前端：Vue 3、TypeScript、Vite、Element Plus、Pinia

## 目录

```text
hengflow-erp/
├── hengflow-api/       # FastAPI 接口、迁移和初始化数据
├── hengflow-admin/     # Vue 管理端
├── docs/               # 安装、配置和开发文档
├── LICENSE
├── NOTICE
└── README.md
```

## 快速开始

HengFlow ERP 不提供 Docker 部署，需要预先安装 Python 3.10、MySQL 5.6+、Redis 6.0+、Node.js 18+ 和 pnpm 8+。

详细步骤见 [源码安装文档](docs/installation.md)。

后端概览：

```bash
cd hengflow-api
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
cd hengflow-admin
pnpm install --frozen-lockfile
pnpm dev
```

默认访问地址：

- 管理端：http://127.0.0.1:5000
- API：http://127.0.0.1:9000
- API 文档：http://127.0.0.1:9000/docs

首次管理员账号和密码由 `hengflow-api/.env` 中的 `INITIAL_ADMIN_USERNAME`、`INITIAL_ADMIN_PASSWORD` 决定。首次登录后请立即修改密码。

## 升级

拉取代码并备份数据库后执行：

```bash
cd hengflow-api
python main.py migrate --env pro
```

再重新构建并发布前端静态文件。详细说明见 [升级文档](docs/upgrade.md)。

## 开源协议与来源

项目使用 MIT License。HengFlow ERP 基于 Kinit 和 vue-element-plus-admin 进行二次开发，原项目版权和许可证信息均予以保留，详情见 [NOTICE](NOTICE)。

欢迎通过 Issue 报告问题，通过 Pull Request 参与开发。提交前请阅读 [贡献指南](CONTRIBUTING.md) 和 [安全策略](SECURITY.md)。
