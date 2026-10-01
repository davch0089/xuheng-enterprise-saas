"""Add ERP data exchange, print templates and attachments.

Revision ID: e4b8a731c9d2
Revises: b7e2c94a6f10
Create Date: 2026-07-20
"""

from alembic import op
import sqlalchemy as sa


revision = "e4b8a731c9d2"
down_revision = "b7e2c94a6f10"
branch_labels = None
depends_on = None


def _base_columns():
    """返回 ERP 公共模型使用的审计与软删除字段。"""

    return (
        sa.Column("id", sa.Integer(), nullable=False, comment="主键ID"),
        sa.Column(
            "create_datetime",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "update_datetime",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.Column("delete_datetime", sa.DateTime(), nullable=True, comment="删除时间"),
        sa.Column(
            "is_delete",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
            comment="是否软删除",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def _menu_tables():
    """声明迁移所需的菜单与角色菜单轻量表。"""

    menu = sa.table(
        "vadmin_auth_menu",
        sa.column("id", sa.Integer),
        sa.column("title", sa.String),
        sa.column("icon", sa.String),
        sa.column("redirect", sa.String),
        sa.column("component", sa.String),
        sa.column("path", sa.String),
        sa.column("disabled", sa.Boolean),
        sa.column("hidden", sa.Boolean),
        sa.column("order", sa.Integer),
        sa.column("menu_type", sa.String),
        sa.column("parent_id", sa.Integer),
        sa.column("perms", sa.String),
        sa.column("noCache", sa.Boolean),
        sa.column("breadcrumb", sa.Boolean),
        sa.column("affix", sa.Boolean),
        sa.column("noTagsView", sa.Boolean),
        sa.column("canTo", sa.Boolean),
        sa.column("alwaysShow", sa.Boolean),
        sa.column("is_delete", sa.Boolean),
    )
    return menu


def _insert_menu(bind, menu, **values) -> int:
    """插入一个带有统一默认属性的菜单节点。"""

    defaults = dict(
        icon=None,
        redirect=None,
        component=None,
        path=None,
        disabled=False,
        hidden=False,
        noCache=False,
        breadcrumb=True,
        affix=False,
        noTagsView=False,
        canTo=False,
        alwaysShow=False,
        is_delete=False,
    )
    defaults.update(values)
    return bind.execute(menu.insert().values(**defaults)).lastrowid


def _install_menus():
    """在 ERP 根菜单下安装文档工具分组、页面和操作权限。"""

    bind = op.get_bind()
    menu = _menu_tables()
    root_id = bind.execute(
        sa.select(menu.c.id).where(
            menu.c.path == "/erp",
            menu.c.menu_type == "0",
            menu.c.is_delete == sa.false(),
        ).limit(1)
    ).scalar()
    if root_id is None:
        raise RuntimeError("ERP root menu /erp does not exist")

    group_id = _insert_menu(
        bind,
        menu,
        title="文档与工具",
        icon="ep:document",
        redirect="/erp/document-tools/data-exchange",
        component="##",
        path="document-tools",
        order=70,
        menu_type="0",
        parent_id=root_id,
        perms=None,
        alwaysShow=True,
    )
    pages = (
        (
            "数据导入导出",
            "ep:sort",
            "views/Erp/System/DataExchange",
            "data-exchange",
            "erp.documents.exchange.list",
            ("erp.documents.exchange.import", "erp.documents.exchange.export"),
        ),
        (
            "打印模板",
            "ep:printer",
            "views/Erp/System/PrintTemplate",
            "print-templates",
            "erp.documents.print.list",
            (
                "erp.documents.print.create",
                "erp.documents.print.update",
                "erp.documents.print.delete",
            ),
        ),
        (
            "附件管理",
            "ep:paperclip",
            "views/Erp/System/Attachment",
            "attachments",
            "erp.documents.attachment.list",
            ("erp.documents.attachment.create", "erp.documents.attachment.delete"),
        ),
    )
    for order, (title, icon, component, path, permission, actions) in enumerate(pages, 1):
        page_id = _insert_menu(
            bind,
            menu,
            title=title,
            icon=icon,
            component=component,
            path=path,
            order=order,
            menu_type="1",
            parent_id=group_id,
            perms=permission,
        )
        for action_order, action_permission in enumerate(actions, 1):
            _insert_menu(
                bind,
                menu,
                title=action_permission.rsplit(".", 1)[-1],
                order=action_order,
                menu_type="2",
                parent_id=page_id,
                perms=action_permission,
            )


def _seed_print_template():
    """安装一个可立即预览和复制修改的通用业务单据模板。"""

    template = sa.table(
        "erp_print_template",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("business_type", sa.String),
        sa.column("content_html", sa.Text),
        sa.column("style_css", sa.Text),
        sa.column("sample_data", sa.JSON),
        sa.column("paper_size", sa.String),
        sa.column("orientation", sa.String),
        sa.column("margin_mm", sa.Integer),
        sa.column("is_default", sa.Boolean),
        sa.column("is_active", sa.Boolean),
        sa.column("version", sa.Integer),
        sa.column("remark", sa.String),
        sa.column("is_delete", sa.Boolean),
    )
    op.get_bind().execute(
        template.insert().values(
            code="ERP_GENERIC_DOCUMENT",
            name="通用业务单据",
            business_type="generic",
            content_html=(
                "<h1>{{ title }}</h1>"
                "<div class='meta'><span>单号：{{ document_no }}</span>"
                "<span>日期：{{ document_date }}</span>"
                "<span>往来单位：{{ partner_name }}</span></div>"
                "<table><thead><tr><th>序号</th><th>商品</th><th>规格</th>"
                "<th>数量</th><th>单位</th><th>单价</th><th>金额</th></tr></thead>"
                "<tbody>{% for line in lines %}<tr><td>{{ loop.index }}</td>"
                "<td>{{ line.product_name }}</td><td>{{ line.specification }}</td>"
                "<td>{{ line.quantity }}</td><td>{{ line.unit_name }}</td>"
                "<td>{{ line.unit_price }}</td><td>{{ line.amount }}</td></tr>"
                "{% endfor %}</tbody></table>"
                "<div class='total'>合计：{{ total_amount }}</div>"
                "<div class='footer'>制单人：{{ creator_name }}　备注：{{ remark }}</div>"
            ),
            style_css=(
                "body{font-family:'Microsoft YaHei',sans-serif;color:#222;font-size:12px}"
                "h1{text-align:center;font-size:22px;margin:0 0 16px}"
                ".meta{display:flex;justify-content:space-between;margin-bottom:10px}"
                "table{width:100%;border-collapse:collapse}"
                "th,td{border:1px solid #333;padding:6px;text-align:center}"
                ".total{text-align:right;font-weight:700;margin-top:12px}"
                ".footer{margin-top:20px}"
            ),
            sample_data={
                "title": "采购入库单",
                "document_no": "RK202607200001",
                "document_date": "2026-07-20",
                "partner_name": "示例供应商",
                "lines": [
                    {
                        "product_name": "示例商品",
                        "specification": "红色 / L",
                        "quantity": 10,
                        "unit_name": "件",
                        "unit_price": "12.50",
                        "amount": "125.00",
                    }
                ],
                "total_amount": "125.00",
                "creator_name": "管理员",
                "remark": "",
            },
            paper_size="A4",
            orientation="portrait",
            margin_mm=10,
            is_default=True,
            is_active=True,
            version=1,
            remark="系统初始化模板，可复制后按业务类型调整",
            is_delete=False,
        )
    )


def upgrade():
    """创建文档中心表、默认打印模板和后台菜单。"""

    op.create_table(
        "erp_attachment",
        sa.Column("business_type", sa.String(60), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_ext", sa.String(30), nullable=True),
        sa.Column("mime_type", sa.String(150), nullable=True),
        sa.Column("file_size", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("storage_type", sa.String(20), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("file_url", sa.String(1000), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.Column("uploaded_by_name", sa.String(100), nullable=True),
        *_base_columns(),
        comment="ERP业务附件",
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_erp_attachment_business_type", "erp_attachment", ["business_type"])
    op.create_index("ix_erp_attachment_business_id", "erp_attachment", ["business_id"])
    op.create_index("ix_erp_attachment_storage_type", "erp_attachment", ["storage_type"])
    op.create_index("ix_erp_attachment_checksum", "erp_attachment", ["checksum"])
    op.create_index("ix_erp_attachment_uploaded_by_id", "erp_attachment", ["uploaded_by_id"])

    op.create_table(
        "erp_print_template",
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("business_type", sa.String(60), nullable=False),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column("style_css", sa.Text(), nullable=True),
        sa.Column("sample_data", sa.JSON(), nullable=True),
        sa.Column("paper_size", sa.String(20), server_default="A4", nullable=False),
        sa.Column("orientation", sa.String(20), server_default="portrait", nullable=False),
        sa.Column("margin_mm", sa.Integer(), server_default="10", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("remark", sa.String(500), nullable=True),
        *_base_columns(),
        sa.UniqueConstraint("code", name="uq_erp_print_template_code"),
        comment="ERP打印模板",
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_erp_print_template_code", "erp_print_template", ["code"])
    op.create_index("ix_erp_print_template_name", "erp_print_template", ["name"])
    op.create_index("ix_erp_print_template_business_type", "erp_print_template", ["business_type"])
    op.create_index("ix_erp_print_template_is_default", "erp_print_template", ["is_default"])
    op.create_index("ix_erp_print_template_is_active", "erp_print_template", ["is_active"])

    op.create_table(
        "erp_data_exchange_task",
        sa.Column("task_type", sa.String(20), nullable=False),
        sa.Column("resource", sa.String(60), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), server_default="processing", nullable=False),
        sa.Column("total_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("success_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("operator_id", sa.Integer(), nullable=True),
        sa.Column("operator_name", sa.String(100), nullable=True),
        *_base_columns(),
        comment="ERP数据导入导出任务",
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_erp_data_exchange_task_task_type", "erp_data_exchange_task", ["task_type"])
    op.create_index("ix_erp_data_exchange_task_resource", "erp_data_exchange_task", ["resource"])
    op.create_index("ix_erp_data_exchange_task_status", "erp_data_exchange_task", ["status"])
    op.create_index("ix_erp_data_exchange_task_operator_id", "erp_data_exchange_task", ["operator_id"])

    _seed_print_template()
    _install_menus()


def downgrade():
    """删除文档中心菜单与业务表。"""

    bind = op.get_bind()
    menu = _menu_tables()
    group_id = bind.execute(
        sa.select(menu.c.id).where(
            menu.c.path == "document-tools",
            menu.c.menu_type == "0",
        ).limit(1)
    ).scalar()
    if group_id is not None:
        page_ids = list(
            bind.execute(sa.select(menu.c.id).where(menu.c.parent_id == group_id)).scalars()
        )
        if page_ids:
            action_ids = list(
                bind.execute(sa.select(menu.c.id).where(menu.c.parent_id.in_(page_ids))).scalars()
            )
            all_ids = action_ids + page_ids + [group_id]
            bind.execute(
                sa.text("DELETE FROM vadmin_auth_role_menus WHERE menu_id IN :ids").bindparams(
                    sa.bindparam("ids", expanding=True)
                ),
                {"ids": all_ids},
            )
            bind.execute(menu.delete().where(menu.c.id.in_(all_ids)))
        else:
            bind.execute(menu.delete().where(menu.c.id == group_id))

    op.drop_table("erp_data_exchange_task")
    op.drop_table("erp_print_template")
    op.drop_table("erp_attachment")
