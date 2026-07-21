"""Add immediate settlement fields to purchase receipts and sales deliveries.

Revision ID: c31f29a8d704
Revises: a85d6c31f942
Create Date: 2026-07-20
"""

from alembic import op
import sqlalchemy as sa


revision = "c31f29a8d704"
down_revision = "a85d6c31f942"
branch_labels = None
depends_on = None


def _add_settlement_columns(table_name: str, link_column: str, link_table: str):
    """为商业单据增加表尾折扣、抹零、即时收付款及来源关联。"""

    with op.batch_alter_table(table_name) as batch:
        batch.add_column(sa.Column("settlement_discount_rate", sa.DECIMAL(10, 4), nullable=False, server_default="100"))
        batch.add_column(sa.Column("settlement_discount_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"))
        batch.add_column(sa.Column("rounding_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"))
        batch.add_column(sa.Column("settlement_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"))
        batch.add_column(sa.Column("current_payment_amount", sa.DECIMAL(20, 4), nullable=False, server_default="0"))
        batch.add_column(sa.Column("settlement_method_id", sa.Integer()))
        batch.add_column(sa.Column("fund_account_id", sa.Integer()))
        batch.add_column(sa.Column(link_column, sa.Integer()))
        batch.create_foreign_key(f"fk_{table_name}_settlement_method", "erp_settlement_method", ["settlement_method_id"], ["id"])
        batch.create_foreign_key(f"fk_{table_name}_fund_account", "erp_fund_account", ["fund_account_id"], ["id"])
        batch.create_foreign_key(f"fk_{table_name}_{link_column}", link_table, [link_column], ["id"])
        batch.create_index(f"ix_{table_name}_fund_account_id", ["fund_account_id"])
        batch.create_index(f"ix_{table_name}_{link_column}", [link_column])
    op.execute(sa.text(
        f"UPDATE {table_name} SET settlement_amount=payable_amount "
        "WHERE settlement_amount=0 AND payable_amount<>0"
    ))


def upgrade():
    """安装采购入库和销售出库的即时结算字段。"""

    _add_settlement_columns("erp_purchase_receipt", "linked_payment_id", "erp_purchase_payment")
    _add_settlement_columns("erp_sales_delivery", "linked_receipt_id", "erp_sales_receipt")


def _drop_settlement_columns(table_name: str, link_column: str):
    """移除商业单据即时结算字段。"""

    with op.batch_alter_table(table_name) as batch:
        batch.drop_index(f"ix_{table_name}_{link_column}")
        batch.drop_index(f"ix_{table_name}_fund_account_id")
        batch.drop_constraint(f"fk_{table_name}_{link_column}", type_="foreignkey")
        batch.drop_constraint(f"fk_{table_name}_fund_account", type_="foreignkey")
        batch.drop_constraint(f"fk_{table_name}_settlement_method", type_="foreignkey")
        for column in (
            link_column, "fund_account_id", "settlement_method_id", "current_payment_amount",
            "settlement_amount", "rounding_amount", "settlement_discount_amount",
            "settlement_discount_rate",
        ):
            batch.drop_column(column)


def downgrade():
    """移除即时结算字段。"""

    _drop_settlement_columns("erp_sales_delivery", "linked_receipt_id")
    _drop_settlement_columns("erp_purchase_receipt", "linked_payment_id")
