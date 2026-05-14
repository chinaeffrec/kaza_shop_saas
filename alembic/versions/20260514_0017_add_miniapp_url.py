"""add miniapp_url to shop_settings

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shop_settings", sa.Column("miniapp_url", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("shop_settings", "miniapp_url")
