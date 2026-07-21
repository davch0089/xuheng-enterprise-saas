"""Unified stock posting engine ledger metadata.

Revision ID: f17c53b8a420
Revises: e06b42a7f319
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa


revision = "f17c53b8a420"
down_revision = "e06b42a7f319"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("erp_inventory_ledger", sa.Column("idempotency_key", sa.String(180), nullable=True, comment="过账幂等键"))
    op.add_column("erp_inventory_ledger", sa.Column("movement_type", sa.String(40), nullable=True, comment="统一库存移动类型"))
    op.add_column("erp_inventory_ledger", sa.Column("business_no", sa.String(60), nullable=True, comment="业务单号快照"))
    op.add_column("erp_inventory_ledger", sa.Column("movement_role", sa.String(30), nullable=False, server_default="main", comment="移动角色"))
    op.add_column("erp_inventory_ledger", sa.Column("reversal_of_id", sa.Integer(), nullable=True, comment="被冲销的原流水"))
    op.add_column("erp_inventory_ledger", sa.Column("batch_no", sa.String(80), nullable=True, comment="批次快照"))
    op.add_column("erp_inventory_ledger", sa.Column("production_date", sa.Date(), nullable=True, comment="生产日期快照"))
    op.add_column("erp_inventory_ledger", sa.Column("expiry_date", sa.Date(), nullable=True, comment="有效期快照"))
    op.add_column("erp_inventory_ledger", sa.Column("serial_numbers", sa.Text(), nullable=True, comment="序列号快照JSON"))

    bind = op.get_bind()
    bind.execute(sa.text("""
        UPDATE erp_inventory_ledger l
        LEFT JOIN erp_inbound_receipt r ON r.id = l.business_id
        LEFT JOIN erp_inbound_receipt_line li ON li.id = l.business_line_id
        SET l.idempotency_key = CONCAT('LEGACY:', l.id),
            l.movement_type = CASE
                WHEN l.direction < 0 OR l.business_type = 'inbound_reversal' THEN 'REVERSAL'
                WHEN r.business_type = 'purchase' THEN 'PURCHASE_IN'
                WHEN r.business_type = 'stock_gain' THEN 'STOCK_GAIN'
                WHEN r.business_type = 'production' THEN 'PRODUCTION_IN'
                WHEN r.business_type = 'transfer' THEN 'TRANSFER_IN'
                ELSE 'OTHER_IN'
            END,
            l.business_no = COALESCE(r.receipt_no, l.movement_no),
            l.movement_role = CASE WHEN l.direction < 0 THEN 'reverse_inbound' ELSE 'inbound' END,
            l.batch_no = li.batch_no,
            l.production_date = li.production_date,
            l.expiry_date = li.expiry_date,
            l.serial_numbers = li.serial_numbers
    """))
    bind.execute(sa.text("""
        UPDATE erp_inventory_ledger reversal
        JOIN erp_inventory_ledger original
          ON original.business_id = reversal.business_id
         AND original.business_line_id = reversal.business_line_id
         AND original.posting_version = reversal.posting_version
         AND original.direction = 1
         AND reversal.direction = -1
        SET reversal.reversal_of_id = original.id,
            reversal.idempotency_key = CONCAT('REVERSE:', original.id),
            reversal.business_type = 'inbound'
        WHERE reversal.business_type = 'inbound_reversal'
    """))
    op.alter_column("erp_inventory_ledger", "idempotency_key", existing_type=sa.String(180), nullable=False)
    op.alter_column("erp_inventory_ledger", "movement_type", existing_type=sa.String(40), nullable=False)
    op.create_unique_constraint("uq_erp_inventory_ledger_idempotency_key", "erp_inventory_ledger", ["idempotency_key"])
    op.create_foreign_key(
        "fk_erp_inventory_ledger_reversal_of",
        "erp_inventory_ledger",
        "erp_inventory_ledger",
        ["reversal_of_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    for column in ("idempotency_key", "movement_type", "business_no", "reversal_of_id"):
        op.create_index(f"ix_erp_inventory_ledger_{column}", "erp_inventory_ledger", [column])

    op.add_column("erp_inventory_serial", sa.Column("source_type", sa.String(30), nullable=True, comment="首次入库来源类型"))
    op.add_column("erp_inventory_serial", sa.Column("source_id", sa.Integer(), nullable=True, comment="首次入库来源ID"))
    op.add_column("erp_inventory_serial", sa.Column("source_line_id", sa.Integer(), nullable=True, comment="首次入库来源行ID"))
    op.add_column("erp_inventory_serial", sa.Column("last_movement_id", sa.Integer(), nullable=True, comment="最后库存流水"))
    bind.execute(sa.text("""
        UPDATE erp_inventory_serial s
        SET s.source_type = 'inbound',
            s.source_id = s.inbound_receipt_id,
            s.source_line_id = s.inbound_line_id,
            s.last_movement_id = (
                SELECT MAX(l.id) FROM erp_inventory_ledger l
                WHERE l.business_type = 'inbound'
                  AND l.business_id = s.inbound_receipt_id
                  AND l.business_line_id = s.inbound_line_id
                  AND l.reversal_of_id IS NULL
            )
    """))
    op.alter_column("erp_inventory_serial", "source_type", existing_type=sa.String(30), nullable=False)
    op.alter_column("erp_inventory_serial", "source_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("erp_inventory_serial", "source_line_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("erp_inventory_serial", "inbound_receipt_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("erp_inventory_serial", "inbound_line_id", existing_type=sa.Integer(), nullable=True)
    op.create_index("ix_erp_inventory_serial_source_type", "erp_inventory_serial", ["source_type"])
    op.create_index("ix_erp_inventory_serial_source_id", "erp_inventory_serial", ["source_id"])
    op.create_foreign_key(
        "fk_erp_inventory_serial_last_movement",
        "erp_inventory_serial",
        "erp_inventory_ledger",
        ["last_movement_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade():
    op.drop_constraint("fk_erp_inventory_serial_last_movement", "erp_inventory_serial", type_="foreignkey")
    op.drop_index("ix_erp_inventory_serial_source_id", table_name="erp_inventory_serial")
    op.drop_index("ix_erp_inventory_serial_source_type", table_name="erp_inventory_serial")
    op.alter_column("erp_inventory_serial", "inbound_line_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("erp_inventory_serial", "inbound_receipt_id", existing_type=sa.Integer(), nullable=False)
    for column in ("last_movement_id", "source_line_id", "source_id", "source_type"):
        op.drop_column("erp_inventory_serial", column)

    op.drop_constraint("fk_erp_inventory_ledger_reversal_of", "erp_inventory_ledger", type_="foreignkey")
    for column in ("reversal_of_id", "business_no", "movement_type", "idempotency_key"):
        op.drop_index(f"ix_erp_inventory_ledger_{column}", table_name="erp_inventory_ledger")
    op.drop_constraint("uq_erp_inventory_ledger_idempotency_key", "erp_inventory_ledger", type_="unique")
    for column in (
        "serial_numbers", "expiry_date", "production_date", "batch_no", "reversal_of_id",
        "movement_role", "business_no", "movement_type", "idempotency_key",
    ):
        op.drop_column("erp_inventory_ledger", column)
