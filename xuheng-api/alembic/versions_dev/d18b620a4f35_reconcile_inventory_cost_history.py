"""Reconcile legacy stock movements with the independent cost engine.

Revision ID: d18b620a4f35
Revises: c7e4a19f2d81
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = "d18b620a4f35"
down_revision = "c7e4a19f2d81"
branch_labels = None
depends_on = None


def upgrade():
    """Backfill missing cost ledgers and reconcile cost balances to stock truth."""

    bind = op.get_bind()
    bind.execute(sa.text("""
        INSERT IGNORE INTO erp_inventory_cost_ledger (
            cost_no, idempotency_key, cost_type, source_type, source_id, source_no,
            source_line_id, cost_role, posting_version, stock_movement_id,
            reversal_of_id, warehouse_id, product_id, quantity, amount,
            balance_quantity_before, balance_quantity_after,
            balance_value_before, balance_value_after,
            average_cost_before, average_cost_after, provisional,
            occurred_at, operator_id, remark, is_delete
        )
        SELECT CONCAT('REPAIR-COST-', l.id), CONCAT('REPAIR-COST:', l.id),
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
               l.occurred_at, l.operator_id, '历史库存流水成本回填', 0
        FROM erp_inventory_ledger l
        LEFT JOIN erp_inventory_cost_ledger c ON c.stock_movement_id = l.id
        WHERE l.is_delete = 0 AND c.id IS NULL
        ORDER BY l.id
    """))
    bind.execute(sa.text("""
        UPDATE erp_inventory_cost_ledger cost_reversal
        JOIN erp_inventory_ledger stock_reversal
          ON stock_reversal.id = cost_reversal.stock_movement_id
        JOIN erp_inventory_cost_ledger cost_original
          ON cost_original.stock_movement_id = stock_reversal.reversal_of_id
        SET cost_reversal.reversal_of_id = cost_original.id
        WHERE stock_reversal.reversal_of_id IS NOT NULL
          AND cost_reversal.reversal_of_id IS NULL
    """))
    bind.execute(sa.text("""
        INSERT INTO erp_inventory_cost_balance (
            warehouse_id, product_id, quantity, inventory_value, average_cost,
            last_cost_ledger_id, needs_revaluation, last_cost_at, is_delete
        )
        SELECT i.warehouse_id, i.product_id, i.quantity, i.inventory_value,
               i.average_cost,
               (SELECT MAX(c.id) FROM erp_inventory_cost_ledger c
                WHERE c.warehouse_id=i.warehouse_id AND c.product_id=i.product_id),
               0, i.last_movement_at, 0
        FROM erp_inventory_balance i
        WHERE i.is_delete = 0
        ON DUPLICATE KEY UPDATE
            quantity=VALUES(quantity), inventory_value=VALUES(inventory_value),
            average_cost=VALUES(average_cost),
            last_cost_ledger_id=VALUES(last_cost_ledger_id),
            last_cost_at=VALUES(last_cost_at), is_delete=0
    """))


def downgrade():
    """Keep reconciled financial history because deleting it would break auditability."""

    pass
