# -*- coding: utf-8 -*-
# @version        : 1.0
# @Create Time    : 2021/10/19 15:47
# @File           : urls.py
# @IDE            : PyCharm
# @desc           : 路由文件

from apps.vadmin.auth.utils.login import app as auth_app
from apps.vadmin.auth.views import app as vadmin_auth_app
from apps.vadmin.system.views import app as vadmin_system_app
from apps.vadmin.record.views import app as vadmin_record_app
from apps.vadmin.workplace.views import app as vadmin_workplace_app
from apps.vadmin.analysis.views import app as vadmin_analysis_app
from apps.vadmin.resource.views import app as vadmin_resource_app
from apps.erp.master.views import app as erp_master_app
from apps.erp.inventory.views import app as erp_inventory_app
from apps.erp.sales.views import app as erp_sales_app
from apps.erp.purchase.views import app as erp_purchase_app
from apps.erp.finance.views import app as erp_finance_app
from apps.erp.dashboard.views import app as erp_dashboard_app
from apps.erp.documents.views import app as erp_documents_app
from apps.xuheng.views import app as xuheng_app


# 引入应用中的路由
urlpatterns = [
    {"ApiRouter": auth_app, "prefix": "/auth", "tags": ["系统认证"]},
    {"ApiRouter": vadmin_auth_app, "prefix": "/vadmin/auth", "tags": ["权限管理"]},
    {"ApiRouter": vadmin_system_app, "prefix": "/vadmin/system", "tags": ["系统管理"]},
    {"ApiRouter": vadmin_record_app, "prefix": "/vadmin/record", "tags": ["记录管理"]},
    {"ApiRouter": vadmin_workplace_app, "prefix": "/vadmin/workplace", "tags": ["工作区管理"]},
    {"ApiRouter": vadmin_analysis_app, "prefix": "/vadmin/analysis", "tags": ["数据分析管理"]},
    {"ApiRouter": vadmin_resource_app, "prefix": "/vadmin/resource", "tags": ["资源管理"]},
    {"ApiRouter": erp_master_app, "prefix": "/erp/master", "tags": ["ERP基础资料"]},
    {"ApiRouter": erp_inventory_app, "prefix": "/erp/inventory", "tags": ["ERP库存管理"]},
    {"ApiRouter": erp_sales_app, "prefix": "/erp/sales", "tags": ["ERP销售管理"]},
    {"ApiRouter": erp_purchase_app, "prefix": "/erp/purchase", "tags": ["ERP采购管理"]},
    {"ApiRouter": erp_finance_app, "prefix": "/erp/finance", "tags": ["ERP财务管理"]},
    {"ApiRouter": erp_dashboard_app, "prefix": "/erp/dashboard", "tags": ["ERP经营驾驶舱"]},
    {"ApiRouter": erp_documents_app, "prefix": "/erp/documents", "tags": ["ERP文档中心"]},
    {"ApiRouter": xuheng_app, "prefix": "/xuheng", "tags": ["序衡履约"]},
]
