"""add CDEK fields to orders

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("cdek_order_uuid",   sa.String(64),  nullable=True))
    op.add_column("orders", sa.Column("cdek_track_number", sa.String(64),  nullable=True))
    op.add_column("orders", sa.Column("cdek_status",       sa.String(64),  nullable=True))
    op.add_column("orders", sa.Column("pvz_code",          sa.String(64),  nullable=True))
    op.add_column("orders", sa.Column("pvz_address",       sa.String(512), nullable=True))
    op.add_column("orders", sa.Column("delivery_cost",     sa.Integer,     nullable=False, server_default="0"))
    op.create_index("ix_orders_cdek_order_uuid", "orders", ["cdek_order_uuid"],
                    postgresql_where=sa.text("cdek_order_uuid IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("ix_orders_cdek_order_uuid", "orders")
    for col in ("delivery_cost", "pvz_address", "pvz_code",
                "cdek_status", "cdek_track_number", "cdek_order_uuid"):
        op.drop_column("orders", col)
