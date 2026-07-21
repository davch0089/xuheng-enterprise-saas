# -*- coding: utf-8 -*-
# @version        : 1.0
# @Create Time    : 2021/10/19 15:47
# @File           : middleware.py
# @IDE            : PyCharm
# @desc           : 中间件

"""
官方文档——中间件：https://fastapi.tiangolo.com/tutorial/middleware/
官方文档——高级中间件：https://fastapi.tiangolo.com/advanced/middleware/
"""
import json
import time
from fastapi import Request, Response
from core.logger import logger
from fastapi import FastAPI
from fastapi.routing import APIRoute
from user_agents import parse
from application.settings import OPERATION_RECORD_METHOD, IGNORE_OPERATION_FUNCTION, \
    DEMO_WHITE_LIST_PATH, DEMO, DEMO_BLACK_LIST_PATH
from utils.response import ErrorResponse
from apps.vadmin.record.crud import OperationRecordDal
from core.database import session_factory
from utils import status


def write_request_log(request: Request, response: Response):
    http_version = f"http/{request.scope['http_version']}"
    content_length = response.raw_headers[0][1]
    process_time = response.headers["X-Process-Time"]
    content = f"basehttp.log_message: '{request.method} {request.url} {http_version}' {response.status_code}" \
              f"{response.charset} {content_length} {process_time}"
    logger.info(content)


def register_request_log_middleware(app: FastAPI):
    """
    记录请求日志中间件
    :param app:
    :return:
    """

    @app.middleware("http")
    async def request_log_middleware(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        write_request_log(request, response)
        return response


def register_operation_record_middleware(app: FastAPI):
    """
    操作记录中间件。

    将已认证用户的增删改请求写入 MySQL；日志写入失败不会影响原业务响应。
    :param app:
    :return:
    """

    def sanitize(value):
        """递归遮蔽密码、令牌等敏感请求字段。"""

        sensitive_keys = {"password", "token", "access_token", "refresh_token", "secret"}
        if isinstance(value, dict):
            return {
                key: "***" if str(key).lower() in sensitive_keys else sanitize(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        return value

    @app.middleware("http")
    async def operation_record_middleware(request: Request, call_next):
        """采集请求上下文，并在业务响应完成后持久化操作日志。"""

        start_time = time.time()
        raw_body = b""
        if request.method in OPERATION_RECORD_METHOD:
            try:
                raw_body = await request.body()
            except Exception:
                raw_body = b""
        response = await call_next(request)
        telephone = request.scope.get('telephone', None)
        user_id = request.scope.get('user_id', None)
        user_name = request.scope.get('user_name', None)
        route = request.scope.get('route')
        if not telephone:
            return response
        elif request.method not in OPERATION_RECORD_METHOD:
            return response
        elif not isinstance(route, APIRoute):
            return response
        elif route.name in IGNORE_OPERATION_FUNCTION:
            return response
        process_time = time.time() - start_time
        user_agent = parse(request.headers.get("user-agent"))
        system = f"{user_agent.os.family} {user_agent.os.version_string}"
        browser = f"{user_agent.browser.family} {user_agent.browser.version_string}"
        query_params = dict(request.query_params.multi_items())
        path_params = request.path_params
        body = None
        if raw_body:
            decoded_body = raw_body[:65536].decode("utf-8", errors="replace")
            try:
                body = sanitize(json.loads(decoded_body))
            except json.JSONDecodeError:
                body = decoded_body
        params = {
            "body": body,
            "query_params": sanitize(query_params) if query_params else None,
            "path_params": path_params if path_params else None,
        }
        content_length = response.headers.get("content-length")
        document = {
            "process_time": process_time,
            "telephone": telephone,
            "user_id": user_id,
            "user_name": user_name,
            "request_api": request.url.__str__(),
            "client_ip": request.client.host,
            "system": system,
            "browser": browser,
            "request_method": request.method,
            "api_path": route.path,
            "summary": route.summary,
            "description": route.description,
            "tags": route.tags,
            "route_name": route.name,
            "status_code": response.status_code,
            "content_length": int(content_length) if content_length and content_length.isdigit() else None,
            "params": json.dumps(params, ensure_ascii=False, default=str)
        }
        try:
            async with session_factory.begin() as db:
                await OperationRecordDal(db).create_data(document)
        except Exception:
            logger.exception("写入 MySQL 操作日志失败")
        return response


def register_demo_env_middleware(app: FastAPI):
    """
    演示环境中间件
    :param app:
    :return:
    """

    @app.middleware("http")
    async def demo_env_middleware(request: Request, call_next):
        path = request.scope.get("path")
        if request.method != "GET":
            print("路由：", path, request.method)
        if DEMO and request.method != "GET":
            if path in DEMO_BLACK_LIST_PATH:
                return ErrorResponse(
                    status=status.HTTP_403_FORBIDDEN,
                    code=status.HTTP_403_FORBIDDEN,
                    msg="演示环境，禁止操作"
                )
            elif path not in DEMO_WHITE_LIST_PATH:
                return ErrorResponse(msg="演示环境，禁止操作")
        return await call_next(request)


def register_jwt_refresh_middleware(app: FastAPI):
    """
    JWT刷新中间件
    :param app:
    :return:
    """

    @app.middleware("http")
    async def jwt_refresh_middleware(request: Request, call_next):
        response = await call_next(request)
        refresh = request.scope.get('if-refresh', 0)
        response.headers["if-refresh"] = str(refresh)
        return response
