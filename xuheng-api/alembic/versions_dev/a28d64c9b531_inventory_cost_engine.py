"""Independent perpetual-average inventory cost engine.

Revision ID: a28d64c9b531
Revises: f17c53b8a420
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa


revision = "a28d64c9b531"
down_revision = "f17c53b8a420"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "erp_inventory_cost_balance",
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("inventory_value", sa.DECIMAL(20, 4), nullable=False, server_default="0"),
        sa.Column("average_cost", sa.DECIMAL(20, 6), nullable=False, server_default="0"),
        sa.Column("last_cost_ledger_id", sa.Integer(), nullable=True, comment="最后成本流水ID"),
        sa.Column(
            "needs_revaluation",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="负库存暂估成本待重算",
        ),
        sa.Column("last_cost_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("create_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("update_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("delete_datetime", sa.DateTime(), nullable=True),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["warehouse_id"], ["erp_warehouse.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["erp_product.id"]),
        sa.UniqueConstraint("warehouse_id", "product_id", name="uq_erp_inventory_cost_balance"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        comment="库存成本余额",
    )
    op.create_index(
        "ix_erp_inventory_cost_balance_warehouse_id",
        "erp_inventory_cost_balance",
        ["warehouse_id"],
    )
    op.create_index(
        "ix_erp_inventory_cost_balance_product_id",
        "erp_inventory_cost_balance",
        ["product_id"],
    )

    op.create_table(
        "erp_inventory_cost_ledger",
        sa.Column("cost_no", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("cost_type", sa.String(30), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("source_no", sa.String(60), nullable=True),
        sa.Column("source_line_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_role", sa.String(30), nullable=False, server_default="main"),
        sa.Column("posting_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("stock_movement_id", sa.Integer(), nullable=True),
        sa.Column("reversal_of_id", sa.Integer(), nullable=True, comment="被冲销的原成本流水"),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("amount", sa.DECIMAL(20, 4), nullable=False),
        sa.Column("balance_quantity_before", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("balance_quantity_after", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("balance_value_before", sa.DECIMAL(20, 4), nullable=False),
        sa.Column("balance_value_after", sa.DECIMAL(20, 4), nullable=False),
        sa.Column("average_cost_before", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("average_cost_after", sa.DECIMAL(20, 6), nullable=False),
        sa.Column("provisional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("operator_id", sa.Integer(), nullable=True),
        sa.Column("remark", sa.String(500), nullable=True),
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("create_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("update_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("delete_datetime", sa.DateTime(), nullable=True),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(
            ["stock_movement_id"], ["erp_inventory_ledger.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reversal_of_id"], ["erp_inventory_cost_ledger.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["warehouse_id"], ["erp_warehouse.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["erp_product.id"]),
        sa.UniqueConstraint("cost_no", name="uq_erp_inventory_cost_ledger_no"),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_erp_inventory_cost_ledger_idempotency_key"
        ),
        sa.UniqueConstraint(
            "stock_movement_id", name="uq_erp_inventory_cost_ledger_stock_movement"
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        comment="不可变库存成本流水",
    )
    for column in (
        "cost_no",
        "idempotency_key",
        "cost_type",
        "source_type",
        "source_id",
        "source_no",
        "stock_movement_id",
        "reversal_of_id",
        "warehouse_id",
        "product_id",
        "occurred_at",
    ):
        op.create_index(
            f"ix_erp_inventory_cost_ledger_{column}",
            "erp_inventory_cost_ledger",
            [column],
        )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO erp_inventory_cost_balance (
                warehouse_id, product_id, quantity, inventory_value, average_cost,
                needs_revaluation, last_cost_at, is_delete
            )
            SELECT warehouse_id, product_id, quantity, inventory_value, average_cost,
                   0, last_movement_at, 0
            FROM erp_inventory_balance
            WHERE is_delete = 0
            """
        )
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO erp_inventory_cost_ledger (
                cost_no, idempotency_key, cost_type, source_type, source_id, source_no,
                source_line_id, cost_role, posting_version, stock_movement_id,
                reversal_of_id, warehouse_id, product_id, quantity, amount,
                balance_quantity_before, balance_quantity_after,
                balance_value_before, balance_value_after,
                average_cost_before, average_cost_after, provisional,
                occurred_at, operator_id, remark, is_delete
            )
            SELECT CONCAT('LEGACY-COST-', l.id),
                   CONCAT('LEGACY-COST:', l.id),
                   CASE
                       WHEN l.movement_type = 'REVERSAL' THEN 'REVERSAL'
                       WHEN l.movement_type = 'TRANSFER_IN' THEN 'TRANSFER_IN'
                       WHEN l.movement_type = 'TRANSFER_OUT' THEN 'TRANSFER_OUT'
                       WHEN l.direction > 0 THEN 'RECEIPT'
                       ELSE 'ISSUE'
                   END,
                   l.business_type, l.business_id, l.business_no,
                   l.business_line_id, l.movement_role, l.posting_version, l.id,
                   NULL, l.warehouse_id, l.product_id, l.quantity, l.amount,
                   l.balance_quantity_before, l.balance_quantity_after,
                   ROUND(l.balance_quantity_before * l.average_cost_before, 4),
                   ROUND(l.balance_quantity_after * l.average_cost_after, 4),
                   l.average_cost_before, l.average_cost_after, 0,
                   l.occurred_at, l.operator_id, '由原库存流水迁移', 0
            FROM erp_inventory_ledger l
            WHERE l.is_delete = 0
            ORDER BY l.id
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE erp_inventory_cost_ledger cost_reversal
            JOIN erp_inventory_ledger stock_reversal
              ON stock_reversal.id = cost_reversal.stock_movement_id
            JOIN erp_inventory_cost_ledger cost_original
              ON cost_original.stock_movement_id = stock_reversal.reversal_of_id
            SET cost_reversal.reversal_of_id = cost_original.id
            WHERE stock_reversal.reversal_of_id IS NOT NULL
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE erp_inventory_cost_balance b
            SET b.last_cost_ledger_id = (
                SELECT MAX(l.id)
                FROM erp_inventory_cost_ledger l
                WHERE l.warehouse_id = b.warehouse_id
                  AND l.product_id = b.product_id
            )
            """
        )
    )


def downgrade():
    op.drop_table("erp_inventory_cost_ledger")
    op.drop_table("erp_inventory_cost_balance")
