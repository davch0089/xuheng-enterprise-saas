# 安全策略

请不要在公开 Issue 中披露可被利用的安全漏洞、密钥或真实业务数据。

部署前必须更换 `SECRET_KEY` 和初始化管理员密码，使用独立的 MySQL、Redis 账号，关闭生产环境 `DEBUG`，限制 `ALLOW_ORIGINS`，通过 HTTPS 暴露服务，并定期备份数据库及附件目录。

如果仓库维护者尚未公布安全邮箱，请通过 GitHub Security Advisory 私下报告漏洞。
