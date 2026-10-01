# 作品集说明

序衡演示企业 SaaS 后台。主线是企业、商品、订单和按数量记账的库存。界面标题是「序衡」。

订单状态是待确认、待发货、已完成、已关闭。发货减少该企业的商品数量，退货把数量加回。商品和订单都带企业编号，查询和保存都限制在当前企业内。

本仓库衍生自 HengFlow ERP，上游还有 Kinit 和 vue-element-plus-admin。许可证与著作权声明在 `LICENSE` 和 `NOTICE`。

## 演示时打开这些页面

1. 企业：`xuheng-admin/src/views/Xuheng/Tenant.vue`
2. 商品：`xuheng-admin/src/views/Xuheng/Product.vue`
3. 订单：`xuheng-admin/src/views/Xuheng/Order.vue`
4. 用户：用户、角色和菜单权限，对应 `xuheng-admin/src/views/Vadmin/Auth/User/User.vue`
5. 运营后台：定时任务 `xuheng-admin/src/views/Vadmin/System/Task/Task.vue`，操作日志 `xuheng-admin/src/views/Vadmin/System/Record/Operation/Operation.vue`

## 和职责的对应

商品、订单、用户和运营后台：

- 企业、商品、订单和数量库存在 `xuheng-api/apps/xuheng`。
- 用户登录、角色和菜单在 `xuheng-api/apps/vadmin/auth`。
- 登录令牌只保存凭据标记，实现在 `xuheng-api/apps/vadmin/auth/utils/credential.py`。

分页、缓存和批量任务：

- 列表分页在 `xuheng-api/core/crud.py` 的 `get_datas`，用 `page` 和 `limit` 做偏移查询。商品、订单和用户列表都走这里。
- 系统配置缓存走 Redis，实现在 `xuheng-api/utils/cache.py`。登录失败次数也记在 Redis，见 `xuheng-api/utils/count.py` 和 `xuheng-api/apps/vadmin/auth/utils/validation/login.py`。
- 定时任务和执行记录在 `xuheng-api/apps/vadmin/system/crud.py` 的 `TaskDal`，任务运行数据在 `scheduler_task_jobs` 和 `scheduler_task_record`。

版本发布和线上排查：

- 数据库变更用 Alembic，命令是 `python main.py migrate`。
- 已审核单据不直接改历史。冲销写反向流水，再次审核增加 `posting_version`，避免同一张单重复过账。
- 操作日志和登录日志用来对照前后端请求。接口文档在 `http://127.0.0.1:9000/docs`。

## 演示顺序

先建企业，再在该企业下录入商品和期初数量，然后创建订单。确认后发货，库存数量下降；对已完成订单做退货，数量加回，订单关闭。用户和定时任务用来说明后台账号、分页查询和批量任务。

登录后如果侧边栏还没有「序衡」，重新登录一次，让菜单从数据库重新加载。网站标题在「系统管理 / 系统设置」里维护，新环境的默认标题由 `xuheng-api/scripts/initialize/initialize.py` 写入。
