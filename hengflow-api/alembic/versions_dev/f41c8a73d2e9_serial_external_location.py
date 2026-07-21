"""Allow an outbound serial number to have no current warehouse.

Revision ID: f41c8a73d2e9
Revises: e2a6f4c91b70
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = "f41c8a73d2e9"
down_revision = "e2a6f4c91b70"
branch_labels = None
depends_on = None


def upgrade():
    """Use NULL warehouse to represent an outbound or voided serial location."""

    op.alter_column(
        "erp_inventory_serial",
        "warehouse_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade():
    """Restore the legacy mandatory warehouse after filling external locations."""

    bind = op.get_bind()
    fallback = bind.execute(
        sa.text("SELECT id FROM erp_warehouse WHERE is_delete = 0 ORDER BY id LIMIT 1")
    ).scalar()
    if fallback is None:
        raise RuntimeError("Cannot downgrade: no warehouse is available for outbound serials")
    bind.execute(
        sa.text("UPDATE erp_inventory_serial SET warehouse_id=:warehouse WHERE warehouse_id IS NULL"),
        {"warehouse": fallback},
    )
    op.alter_column(
        "erp_inventory_serial",
        "warehouse_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
