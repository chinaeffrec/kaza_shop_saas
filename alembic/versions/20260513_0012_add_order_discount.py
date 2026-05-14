"""add promo_code and discount columns to orders

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("promo_code", sa.String(50), nullable=True))
    op.add_column("orders", sa.Column("discount", sa.Integer, nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("orders", "discount")
    op.drop_column("orders", "promo_code")
