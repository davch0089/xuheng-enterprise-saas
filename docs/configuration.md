# 配置说明

后端配置来自 `xuheng-api/.env`。仓库只提交 `.env.example`，严禁提交真实 `.env`。

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `DEBUG` | 是 | 生产环境必须为 `false` |
| `SECRET_KEY` | 是 | JWT 签名随机密钥 |
| `DATABASE_URL` | 是 | SQLAlchemy MySQL 异步连接地址 |
| `REDIS_ENABLED` | 否 | 是否启用 Redis |
| `REDIS_URL` | 启用时 | Redis 连接地址 |
| `ALLOW_ORIGINS` | 是 | 逗号分隔的前端来源 |
| `INITIAL_ADMIN_USERNAME` | 首次初始化 | 11 位管理员登录账号 |
| `INITIAL_ADMIN_PASSWORD` | 首次初始化 | 管理员首次密码 |
| `OSS_*` | 否 | 阿里云 OSS 附件配置 |

`INITIAL_ADMIN_*` 只在空数据库执行 `init` 时使用，不会在每次启动时覆盖管理员。

前端开发代理由 `xuheng-admin/.env.dev` 中的 `VITE_API_TARGET` 控制。生产构建不把数据库、JWT 或 OSS 密钥写入前端环境变量。
