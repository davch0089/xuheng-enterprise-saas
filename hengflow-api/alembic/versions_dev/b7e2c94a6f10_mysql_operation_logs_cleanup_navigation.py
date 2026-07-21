"""Store operation logs in MySQL and simplify the default navigation.

Revision ID: b7e2c94a6f10
Revises: c31f29a8d704
Create Date: 2026-07-20
"""

from alembic import op
import sqlalchemy as sa


revision = "b7e2c94a6f10"
down_revision = "c31f29a8d704"
branch_labels = None
depends_on = None


REMOVED_COMPONENTS = (
    "views/Dashboard/Map",
    "views/Vadmin/System/Record/Task/Task",
    "views/Vadmin/Help/IssueCategory/IssueCategory",
    "views/Vadmin/Help/Issue/Issue",
    "views/Vadmin/Help/Issue/components/Write",
)


def upgrade():
    """创建 MySQL 操作日志表，并隐藏废弃导航入口。"""

    op.create_table(
        "vadmin_record_operation",
        sa.Column("telephone", sa.String(length=255), nullable=True, comment="手机号"),
        sa.Column("user_id", sa.Integer(), nullable=True, comment="操作人 ID"),
        sa.Column("user_name", sa.String(length=255), nullable=True, comment="操作人"),
        sa.Column("status_code", sa.Integer(), nullable=True, comment="HTTP 状态码"),
        sa.Column("client_ip", sa.String(length=50), nullable=True, comment="客户端 IP"),
        sa.Column("request_method", sa.String(length=10), nullable=True, comment="请求方法"),
        sa.Column("request_api", sa.Text(), nullable=True, comment="完整请求地址"),
        sa.Column("api_path", sa.String(length=255), nullable=True, comment="接口路由"),
        sa.Column("system", sa.String(length=100), nullable=True, comment="操作系统"),
        sa.Column("browser", sa.String(length=100), nullable=True, comment="浏览器"),
        sa.Column("summary", sa.String(length=255), nullable=True, comment="操作摘要"),
        sa.Column("route_name", sa.String(length=255), nullable=True, comment="接口函数"),
        sa.Column("description", sa.Text(), nullable=True, comment="接口描述"),
        sa.Column("tags", sa.JSON(), nullable=True, comment="接口标签"),
        sa.Column("process_time", sa.Float(), nullable=True, comment="处理耗时（秒）"),
        sa.Column("params", sa.Text(), nullable=True, comment="请求参数"),
        sa.Column("content_length", sa.Integer(), nullable=True, comment="响应大小"),
        sa.Column("id", sa.Integer(), nullable=False, comment="主键ID"),
        sa.Column("create_datetime", sa.DateTime(), server_default=sa.text("now()"), nullable=False, comment="创建时间"),
        sa.Column("update_datetime", sa.DateTime(), server_default=sa.text("now()"), nullable=False, comment="更新时间"),
        sa.Column("delete_datetime", sa.DateTime(), nullable=True, comment="删除时间"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="是否软删除"),
        sa.PrimaryKeyConstraint("id"),
        comment="操作日志",
    )
    op.create_index("ix_vadmin_record_operation_telephone", "vadmin_record_operation", ["telephone"])
    op.create_index("ix_vadmin_record_operation_user_id", "vadmin_record_operation", ["user_id"])
    op.create_index("ix_vadmin_record_operation_create_datetime", "vadmin_record_operation", ["create_datetime"])

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE vadmin_auth_menu SET title='经营仪表盘' "
            "WHERE component='views/Dashboard/Workplace' AND is_delete=0"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE vadmin_auth_menu SET is_delete=1, delete_datetime=NOW() "
            "WHERE path='/help' OR component IN :components"
        ).bindparams(sa.bindparam("components", expanding=True)),
        {"components": REMOVED_COMPONENTS},
    )


def downgrade():
    """恢复原导航入口并删除 MySQL 操作日志表。"""

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE vadmin_auth_menu SET title='工作台' "
            "WHERE component='views/Dashboard/Workplace'"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE vadmin_auth_menu SET is_delete=0, delete_datetime=NULL "
            "WHERE path='/help' OR component IN :components"
        ).bindparams(sa.bindparam("components", expanding=True)),
        {"components": REMOVED_COMPONENTS},
    )
    op.drop_index("ix_vadmin_record_operation_create_datetime", table_name="vadmin_record_operation")
    op.drop_index("ix_vadmin_record_operation_user_id", table_name="vadmin_record_operation")
    op.drop_index("ix_vadmin_record_operation_telephone", table_name="vadmin_record_operation")
    op.drop_table("vadmin_record_operation")
