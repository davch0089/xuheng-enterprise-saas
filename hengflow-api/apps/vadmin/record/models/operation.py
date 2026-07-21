#!/usr/bin/python
# -*- coding: utf-8 -*-

"""MySQL 操作日志模型。"""

from sqlalchemy import Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.db_base import BaseModel


class VadminOperationRecord(BaseModel):
    """保存已认证用户对系统执行的增删改操作。"""

    __tablename__ = "vadmin_record_operation"
    __table_args__ = ({"comment": "操作日志"},)

    telephone: Mapped[str | None] = mapped_column(String(255), index=True, comment="手机号")
    user_id: Mapped[int | None] = mapped_column(Integer, index=True, comment="操作人 ID")
    user_name: Mapped[str | None] = mapped_column(String(255), comment="操作人")
    status_code: Mapped[int | None] = mapped_column(Integer, comment="HTTP 状态码")
    client_ip: Mapped[str | None] = mapped_column(String(50), comment="客户端 IP")
    request_method: Mapped[str | None] = mapped_column(String(10), comment="请求方法")
    request_api: Mapped[str | None] = mapped_column(Text, comment="完整请求地址")
    api_path: Mapped[str | None] = mapped_column(String(255), comment="接口路由")
    system: Mapped[str | None] = mapped_column(String(100), comment="操作系统")
    browser: Mapped[str | None] = mapped_column(String(100), comment="浏览器")
    summary: Mapped[str | None] = mapped_column(String(255), comment="操作摘要")
    route_name: Mapped[str | None] = mapped_column(String(255), comment="接口函数")
    description: Mapped[str | None] = mapped_column(Text, comment="接口描述")
    tags: Mapped[list | None] = mapped_column(JSON, comment="接口标签")
    process_time: Mapped[float | None] = mapped_column(Float, comment="处理耗时（秒）")
    params: Mapped[str | None] = mapped_column(Text, comment="请求参数")
    content_length: Mapped[int | None] = mapped_column(Integer, comment="响应大小")
