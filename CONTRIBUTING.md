# 贡献指南

感谢参与 序衡。

1. Fork 仓库并从最新主分支创建功能分支。
2. 不要提交 `.env`、日志、附件、数据库备份或真实业务数据。
3. 后端业务逻辑放入对应领域的 `services`，HTTP 层只负责鉴权和参数转换。
4. 数据库变化必须提交 Alembic 迁移，不要修改已经发布的历史迁移。
5. 新增对象和函数应说明职责、输入以及业务副作用。

提交前执行：

```bash
cd xuheng-api
python -m compileall -q apps application core

cd ../xuheng-admin
pnpm lint:eslint
pnpm ts:check
pnpm build:pro
```

Pull Request 请描述业务背景、数据结构变化、验证方式和兼容性影响。
