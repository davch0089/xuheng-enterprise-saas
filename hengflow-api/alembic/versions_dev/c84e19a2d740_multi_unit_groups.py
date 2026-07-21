"""Replace product-bound conversions with reusable hierarchical unit groups.

Revision ID: c84e19a2d740
Revises: b72d08f6c931
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa


revision = "c84e19a2d740"
down_revision = "b72d08f6c931"
branch_labels = None
depends_on = None


def base_columns():
    return [
        sa.Column("id", sa.Integer(), primary_key=True, comment="主键ID"),
        sa.Column("create_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("update_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("delete_datetime", sa.DateTime(), nullable=True),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.false()),
    ]


def upgrade():
    op.drop_table("erp_unit_conversion")
    op.create_table(
        "erp_unit_group",
        sa.Column("name", sa.String(100), nullable=False, comment="方案名称"),
        sa.Column("primary_unit_id", sa.Integer(), nullable=False, comment="主单位"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true(), comment="是否启用"),
        sa.Column("remark", sa.String(500), nullable=True, comment="备注"),
        *base_columns(),
        sa.ForeignKeyConstraint(["primary_unit_id"], ["erp_unit.id"]),
        sa.UniqueConstraint("name", name="uq_erp_unit_group_name"),
        comment="多单位方案",
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_erp_unit_group_name", "erp_unit_group", ["name"])
    op.create_table(
        "erp_unit_group_item",
        sa.Column("group_id", sa.Integer(), nullable=False, comment="多单位方案"),
        sa.Column("unit_id", sa.Integer(), nullable=False, comment="子单位"),
        sa.Column("parent_id", sa.Integer(), nullable=True, comment="上级明细；为空时上级为主单位"),
        sa.Column("factor", sa.DECIMAL(20, 8), nullable=False, comment="1上级单位等于当前单位数量"),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0", comment="排序"),
        *base_columns(),
        sa.ForeignKeyConstraint(["group_id"], ["erp_unit_group.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unit_id"], ["erp_unit.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["erp_unit_group_item.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("group_id", "unit_id", name="uq_erp_unit_group_item_unit"),
        comment="多单位方案明细",
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.add_column(
        "erp_product",
        sa.Column("multi_unit_enabled", sa.Boolean(), nullable=False, server_default=sa.false(), comment="是否启用多单位"),
    )
    op.add_column(
        "erp_product",
        sa.Column("unit_group_id", sa.Integer(), nullable=True, comment="多单位方案"),
    )
    op.create_foreign_key(
        "fk_erp_product_unit_group_id", "erp_product", "erp_unit_group", ["unit_group_id"], ["id"]
    )


def downgrade():
    op.drop_constraint("fk_erp_product_unit_group_id", "erp_product", type_="foreignkey")
    op.drop_column("erp_product", "unit_group_id")
    op.drop_column("erp_product", "multi_unit_enabled")
    op.drop_table("erp_unit_group_item")
    op.drop_index("ix_erp_unit_group_name", table_name="erp_unit_group")
    op.drop_table("erp_unit_group")
    op.create_table(
        "erp_unit_conversion",
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("from_unit_id", sa.Integer(), nullable=False),
        sa.Column("to_unit_id", sa.Integer(), nullable=False),
        sa.Column("factor", sa.DECIMAL(20, 8), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.String(500), nullable=True),
        *base_columns(),
        sa.ForeignKeyConstraint(["product_id"], ["erp_product.id"]),
        sa.ForeignKeyConstraint(["from_unit_id"], ["erp_unit.id"]),
        sa.ForeignKeyConstraint(["to_unit_id"], ["erp_unit.id"]),
        sa.UniqueConstraint("product_id", "from_unit_id", "to_unit_id", name="uq_erp_unit_conversion"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
