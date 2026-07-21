# 升级

1. 停止写入业务单据并备份 MySQL 数据库与本地附件目录。
2. 拉取新版本代码并激活后端虚拟环境。
3. 安装新增依赖并执行已发布迁移。

```bash
cd hengflow-api
pip install -r requirements.txt
python main.py migrate --env pro
```

4. 重新构建前端并替换静态文件。

```bash
cd ../hengflow-admin
pnpm install --frozen-lockfile
pnpm build:pro
```

5. 重启 API，重新登录并检查菜单、库存余额、成本余额及会计期间。

不要在生产服务器执行 `revision` 命令，也不要修改已经发布的历史迁移文件。
