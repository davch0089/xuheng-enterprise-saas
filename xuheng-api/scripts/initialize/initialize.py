#!/usr/bin/python
# -*- coding: utf-8 -*-
# @version        : 1.0
# @Create Time    : 2022/11/23 11:21 
# @File           : initialize.py
# @IDE            : PyCharm
# @desc           : 简要说明

from enum import Enum
from sqlalchemy import insert
from core.database import db_getter
from utils.excel.excel_manage import ExcelManage
from application.settings import (
    BASE_DIR,
    INITIAL_ADMIN_PASSWORD,
    INITIAL_ADMIN_USERNAME,
    VERSION,
)
import os
from apps.vadmin.auth import models as auth_models
from apps.vadmin.system import models as system_models
import subprocess


class Environment(str, Enum):
    dev = "dev"
    pro = "pro"


class InitializeData:
    """
    初始化数据

    生成步骤：
        1. 读取数据
        2. 获取数据库
        3. 创建数据
    """

    SCRIPT_DIR = os.path.join(BASE_DIR, 'scripts', 'initialize')

    def __init__(self):
        self.sheet_names = []
        self.datas = {}
        self.ex = None
        self.db = None
        self.__serializer_data()
        self.__get_sheet_data()

    @classmethod
    def upgrade_model(cls, env: Environment = Environment.pro):
        """
        将已有 Alembic 迁移升级到最新版本。
        """
        subprocess.check_call(['alembic', '--name', f'{env.value}', 'upgrade', 'head'], cwd=BASE_DIR)
        print(f"环境：{env}  {VERSION} 数据库表迁移完成")

    @classmethod
    def create_revision(cls, message: str, env: Environment = Environment.dev):
        """仅供开发者根据模型变化生成新的 Alembic 迁移文件。"""

        subprocess.check_call(
            [
                'alembic', '--name', f'{env.value}', 'revision', '--autogenerate',
                '-m', message,
            ],
            cwd=BASE_DIR,
        )

    def __serializer_data(self):
        """
        序列化数据，将excel数据转为python对象
        """
        self.ex = ExcelManage()
        self.ex.open_workbook(os.path.join(self.SCRIPT_DIR, 'data', 'init.xlsx'), read_only=True)
        self.sheet_names = self.ex.get_sheets()

    def __get_sheet_data(self):
        """
        获取工作区数据
        """
        for sheet in self.sheet_names:
            sheet_data = []
            self.ex.open_sheet(sheet)
            headers = self.ex.get_header()
            datas = self.ex.readlines(min_row=2, max_col=len(headers))
            for row in datas:
                sheet_data.append(dict(zip(headers, row)))
            self.datas[sheet] = sheet_data
        self.__apply_project_defaults()

    def __apply_project_defaults(self):
        """覆盖上游初始化数据中的品牌和演示管理员凭据。"""

        users = self.datas.get("vadmin_auth_user", [])
        if users:
            users[0]["telephone"] = INITIAL_ADMIN_USERNAME
            users[0]["name"] = "系统管理员"
            users[0]["nickname"] = "管理员"
            users[0]["password"] = auth_models.VadminUser.get_password_hash(
                INITIAL_ADMIN_PASSWORD
            )
            users[0]["is_reset_password"] = False

        settings = {
            item.get("config_key"): item
            for item in self.datas.get("vadmin_system_settings", [])
        }
        if "web_title" in settings:
            settings["web_title"]["config_value"] = "序衡"
        if "web_desc" in settings:
            settings["web_desc"]["config_value"] = "序衡，面向商品、订单、用户与运营后台的企业 SaaS 管理系统"
        if "web_copyright" in settings:
            settings["web_copyright"]["config_value"] = "序衡演示 · 基于 HengFlow ERP"
        if "web_icp_number" in settings:
            settings["web_icp_number"]["config_value"] = ""

    async def __generate_data(self, table_name: str, model):
        """
        生成数据

        :param table_name: 表名
        :param model: 数据表模型
        """

        print(f"开始生成: {table_name}")

        async_session = db_getter()

        print("获取 session generator")

        db = await async_session.__anext__()

        print("获取数据库 session 成功")

        datas = self.datas.get(table_name)

        print(f"{table_name} 数据数量:", len(datas))

        await db.execute(insert(model), datas)

        print(f"{table_name} insert成功")

        await db.commit()

        print(f"{table_name} 表数据已生成")
        

    async def generate_dept(self):
        """
        生成部门详情数据
        """
        await self.__generate_data("vadmin_auth_dept", auth_models.VadminDept)

    async def generate_user_dept(self):
        """
        生成用户关联部门详情数据
        """
        await self.__generate_data("vadmin_auth_user_depts", auth_models.vadmin_auth_user_depts)

    async def generate_menu(self):
        """
        生成菜单数据
        """
        removed_components = {
            "views/Dashboard/Map",
            "views/Vadmin/System/Record/Task/Task",
            "views/Vadmin/Help/IssueCategory/IssueCategory",
            "views/Vadmin/Help/Issue/Issue",
            "views/Vadmin/Help/Issue/components/Write",
        }
        self.datas["vadmin_auth_menu"] = [
            data
            for data in self.datas.get("vadmin_auth_menu", [])
            if data.get("path") != "/help" and data.get("component") not in removed_components
        ]
        for data in self.datas["vadmin_auth_menu"]:
            if data.get("component") == "views/Dashboard/Workplace":
                data["title"] = "经营仪表盘"
        await self.__generate_data("vadmin_auth_menu", auth_models.VadminMenu)

    async def generate_role(self):
        """
        生成角色
        """
        await self.__generate_data("vadmin_auth_role", auth_models.VadminRole)

    async def generate_user(self):
        """
        生成用户
        """
        await self.__generate_data("vadmin_auth_user", auth_models.VadminUser)

    async def generate_user_role(self):
        """
        生成用户
        """
        await self.__generate_data("vadmin_auth_user_roles", auth_models.vadmin_auth_user_roles)

    async def generate_system_tab(self):
        """
        生成系统配置分类数据
        """
        await self.__generate_data("vadmin_system_settings_tab", system_models.VadminSystemSettingsTab)

    async def generate_system_config(self):
        """
        生成系统配置数据
        """
        await self.__generate_data("vadmin_system_settings", system_models.VadminSystemSettings)

    async def generate_dict_type(self):
        """
        生成字典类型数据
        """
        await self.__generate_data("vadmin_system_dict_type", system_models.VadminDictType)

    async def generate_dict_details(self):
        """
        生成字典详情数据
        """
        await self.__generate_data("vadmin_system_dict_details", system_models.VadminDictDetails)

    async def run(self, env: Environment = Environment.pro):
        """
        执行初始化工作
        """
        # self.upgrade_model(env)
        print("跳过数据库迁移")
        await self.generate_menu()
        await self.generate_role()
        await self.generate_dept()
        await self.generate_user()
        await self.generate_user_dept()
        await self.generate_user_role()
        await self.generate_system_tab()
        await self.generate_dict_type()
        await self.generate_system_config()
        await self.generate_dict_details()
        print(f"环境：{env} {VERSION} 数据已初始化完成")
