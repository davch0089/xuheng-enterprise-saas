"""Add product SPU and normalized SKU attributes.

Revision ID: c91d7e4a2b60
Revises: a7c4e91d5b20
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa


revision = "c91d7e4a2b60"
down_revision = "a7c4e91d5b20"
branch_labels = None
depends_on = None
OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


def base_columns():
    """返回 HengFlow ERP 业务表统一使用的审计字段。"""

    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("create_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("update_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("delete_datetime", sa.DateTime()),
        sa.Column("is_delete", sa.Boolean(), server_default=sa.false(), nullable=False),
    ]


def upgrade():
    """创建 SPU/属性表，并把每个现有商品无损转换为一个默认 SKU。"""

    op.create_table(
        "erp_product_spu",
        *base_columns(),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("brand", sa.String(100)),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("remark", sa.Text()),
        sa.ForeignKeyConstraint(["category_id"], ["erp_product_category.id"]),
        sa.UniqueConstraint("code", name="uq_erp_product_spu_code"),
        comment="商品SPU档案",
        **OPTIONS,
    )
    op.create_index("ix_erp_product_spu_code", "erp_product_spu", ["code"])
    op.create_index("ix_erp_product_spu_name", "erp_product_spu", ["name"])

    op.create_table(
        "erp_product_attribute",
        *base_columns(),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.UniqueConstraint("name", name="uq_erp_product_attribute_name"),
        comment="SKU属性定义",
        **OPTIONS,
    )
    op.create_index("ix_erp_product_attribute_name", "erp_product_attribute", ["name"])

    op.create_table(
        "erp_product_attribute_value",
        *base_columns(),
        sa.Column("attribute_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.String(100), nullable=False),
        sa.Column("order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.ForeignKeyConstraint(["attribute_id"], ["erp_product_attribute.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("attribute_id", "value", name="uq_erp_product_attribute_value"),
        comment="SKU属性值",
        **OPTIONS,
    )
    op.create_index("ix_erp_product_attribute_value_attribute_id", "erp_product_attribute_value", ["attribute_id"])
    op.create_index("ix_erp_product_attribute_value_value", "erp_product_attribute_value", ["value"])

    with op.batch_alter_table("erp_product") as batch:
        batch.add_column(sa.Column("spu_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("variant_name", sa.String(200), nullable=True))
        batch.add_column(sa.Column("variant_key", sa.String(500), nullable=True))
        batch.add_column(sa.Column("is_default_sku", sa.Boolean(), server_default=sa.false(), nullable=False))

    op.execute(sa.text(
        "INSERT INTO erp_product_spu "
        "(code, name, category_id, brand, is_active, remark, create_datetime, update_datetime, is_delete) "
        "SELECT code, name, category_id, brand, is_active, remark, create_datetime, update_datetime, is_delete "
        "FROM erp_product"
    ))
    op.execute(sa.text(
        "UPDATE erp_product p JOIN erp_product_spu s ON s.code = p.code "
        "SET p.spu_id = s.id, p.variant_name = COALESCE(NULLIF(p.specification, ''), '默认规格'), "
        "p.variant_key = '__DEFAULT__', p.is_default_sku = 1"
    ))

    with op.batch_alter_table("erp_product") as batch:
        batch.alter_column("spu_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("variant_name", existing_type=sa.String(200), nullable=False)
        batch.alter_column("variant_key", existing_type=sa.String(500), nullable=False)
        batch.create_foreign_key("fk_erp_product_spu_id", "erp_product_spu", ["spu_id"], ["id"])
        batch.create_unique_constraint("uq_erp_product_spu_variant", ["spu_id", "variant_key"])
        batch.create_index("ix_erp_product_spu_id", ["spu_id"])

    op.create_table(
        "erp_product_sku_attribute",
        *base_columns(),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("attribute_id", sa.Integer(), nullable=False),
        sa.Column("value_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["erp_product.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attribute_id"], ["erp_product_attribute.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["value_id"], ["erp_product_attribute_value.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("product_id", "attribute_id", name="uq_erp_product_sku_attribute"),
        comment="SKU属性组合",
        **OPTIONS,
    )
    op.create_index("ix_erp_product_sku_attribute_product_id", "erp_product_sku_attribute", ["product_id"])


def downgrade():
    """移除 SKU 分组结构，但保留原 erp_product 商品数据。"""

    op.drop_table("erp_product_sku_attribute")
    with op.batch_alter_table("erp_product") as batch:
        batch.drop_index("ix_erp_product_spu_id")
        batch.drop_constraint("uq_erp_product_spu_variant", type_="unique")
        batch.drop_constraint("fk_erp_product_spu_id", type_="foreignkey")
        batch.drop_column("is_default_sku")
        batch.drop_column("variant_key")
        batch.drop_column("variant_name")
        batch.drop_column("spu_id")
    op.drop_table("erp_product_attribute_value")
    op.drop_table("erp_product_attribute")
    op.drop_table("erp_product_spu")
