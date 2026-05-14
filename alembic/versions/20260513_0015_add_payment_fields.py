"""add YooKassa payment fields to orders

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("payment_id",     sa.String(64),  nullable=True))
    op.add_column("orders", sa.Column("payment_status", sa.String(32),  nullable=True))
    op.add_column("orders", sa.Column("refund_id",      sa.String(64),  nullable=True))
    op.create_index("ix_orders_payment_id", "orders", ["payment_id"],
                    postgresql_where=sa.text("payment_id IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("ix_orders_payment_id", "orders")
    for col in ("refund_id", "payment_status", "payment_id"):
        op.drop_column("orders", col)
