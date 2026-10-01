# 序衡

Vue 3 管理端，用于商品、订单、用户和运营后台。作品集对照见仓库根目录 `docs/portfolio.md`。

```bash
pnpm install --frozen-lockfile
pnpm dev
```

开发环境通过 `VITE_API_TARGET` 将 `/api`、`/vadmin` 和 `/media` 代理到 FastAPI。生产构建：

```bash
pnpm build:pro
```

构建结果默认位于 `dist-pro`。生产 Web 服务器需要将 SPA 未命中的页面回退到 `index.html`，并正确反向代理后端路径。完整说明见仓库根目录 `docs/installation.md`。
