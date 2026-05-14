"""add i18n fields to shop_settings

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shop_settings", sa.Column(
        "default_language", sa.String(8), nullable=False, server_default="ru"
    ))
    op.add_column("shop_settings", sa.Column(
        "shop_languages", sa.String(64), nullable=False, server_default="ru"
    ))


def downgrade() -> None:
    op.drop_column("shop_settings", "shop_languages")
    op.drop_column("shop_settings", "default_language")
