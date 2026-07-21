"""Ensure ERP tables use transactional InnoDB storage.

Revision ID: b72d08f6c931
Revises: 9c1f2a7e4b11
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa


revision = "b72d08f6c931"
down_revision = "9c1f2a7e4b11"
branch_labels = None
depends_on = None


ERP_TABLES = (
    "erp_product_category", "erp_unit", "erp_settlement_method", "erp_warehouse",
    "erp_employee", "erp_product", "erp_unit_conversion", "erp_customer", "erp_supplier",
)


def upgrade():
    for table in ERP_TABLES:
        op.execute(sa.text(f"ALTER TABLE `{table}` ENGINE=InnoDB"))

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    required = {
        "erp_product_category": [("parent_id", "erp_product_category", "id", "SET NULL")],
        "erp_product": [("category_id", "erp_product_category", "id", None), ("base_unit_id", "erp_unit", "id", None)],
        "erp_unit_conversion": [
            ("product_id", "erp_product", "id", None),
            ("from_unit_id", "erp_unit", "id", None),
            ("to_unit_id", "erp_unit", "id", None),
        ],
        "erp_customer": [("settlement_method_id", "erp_settlement_method", "id", None)],
        "erp_supplier": [("settlement_method_id", "erp_settlement_method", "id", None)],
    }
    for table, constraints in required.items():
        existing = {tuple(item["constrained_columns"]) for item in inspector.get_foreign_keys(table)}
        for column, target_table, target_column, ondelete in constraints:
            if (column,) not in existing:
                op.create_foreign_key(
                    f"fk_{table}_{column}", table, target_table, [column], [target_column], ondelete=ondelete
                )


def downgrade():
    # Deliberately keep InnoDB: reverting to a non-transactional engine risks accounting data.
    pass
