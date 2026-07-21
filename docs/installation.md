# 源码安装

HengFlow ERP。本说明以同一台服务器部署 MySQL、Redis、FastAPI 和前端静态文件为例。

## 1. 环境要求

- Python 3.10
- MySQL 5.6 或更高版本
- Redis 6.0 或更高版本
- Node.js 18 或更高版本
- pnpm 8 或更高版本

推荐在 Linux 服务器使用 systemd 管理 API，并使用 Nginx 或其他 Web 服务器发布前端。Windows 开发环境可以直接运行启动命令。

## 2. 创建数据库


```sql
CREATE DATABASE hengflow CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'hengflow'@'localhost' IDENTIFIED BY '请替换为强密码';
GRANT ALL PRIVILEGES ON hengflow.* TO 'hengflow'@'localhost';
FLUSH PRIVILEGES;
```

## 3. 安装后端

```bash
cd hengflow-api
python -m venv venv
```

激活虚拟环境：

```bash
# Linux / macOS
source venv/bin/activate

# Windows PowerShell
venv\Scripts\Activate.ps1
```

安装并配置：

```bash
pip install -r requirements.txt
cp .env.example .env
```

Windows 没有 `cp` 时执行：

```powershell
Copy-Item .env.example .env
```

至少修改以下配置：

```dotenv
DEBUG=false
SECRET_KEY=使用密码生成器生成的长随机字符串
DATABASE_URL=mysql+asyncmy://hengflow:数据库密码@127.0.0.1:3306/hengflow
REDIS_URL=redis://127.0.0.1:6379/1
ALLOW_ORIGINS=https://你的管理端域名
INITIAL_ADMIN_USERNAME=13800000000
INITIAL_ADMIN_PASSWORD=首次登录密码
```

首次只对空数据库执行：

```bash
python main.py init --env pro
```

该命令会执行已发布的数据库迁移并写入权限、菜单及管理员初始化数据，不会自动生成新迁移。启动 API：

```bash
python main.py run --host 0.0.0.0 --port 9000
```

生产环境建议使用进程管理器启动 Uvicorn/Gunicorn，并限制 API 端口只能由反向代理访问。

## 4. 安装前端

```bash
cd hengflow-admin
pnpm install --frozen-lockfile
pnpm dev
```

开发服务器默认地址为 `http://127.0.0.1:5000`，通过 `.env.dev` 中的 `VITE_API_TARGET` 连接后端。

生产构建：

```bash
pnpm build:pro
```

将 `dist-pro` 发布到 Web 服务器。以 Nginx 为例，核心规则如下：

```nginx
location / {
    try_files $uri $uri/ /index.html;
}

location /api/ {
    proxy_pass http://127.0.0.1:9000/;
}

location /vadmin/ {
    proxy_pass http://127.0.0.1:9000/vadmin/;
}

location /media/ {
    proxy_pass http://127.0.0.1:9000/media/;
}
```

## 5. 首次登录

使用 `.env` 中配置的 `INITIAL_ADMIN_USERNAME`、`INITIAL_ADMIN_PASSWORD` 登录，并立即修改密码。

如果菜单没有刷新，请退出后重新登录。API 文档默认位于 `/docs`。

## 6. 常见问题

- 数据库连接失败：确认 MySQL 用户授权主机与 `DATABASE_URL` 一致。
- 登录接口失败：确认 Redis 已启动；不使用 Redis 时将 `REDIS_ENABLED=false`。
- 前端请求 404：检查 `/api` 的反向代理是否移除了 `/api` 前缀。
- 页面刷新 404：Web 服务器必须把未知前端路由回退到 `index.html`。
- OSS 上传失败：未配置 OSS 时请选择本地附件存储。
