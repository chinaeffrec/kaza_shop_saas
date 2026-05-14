"""add YooKassa fields to shop_settings

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shop_settings", sa.Column("yookassa_enabled",    sa.Boolean,     nullable=False, server_default="false"))
    op.add_column("shop_settings", sa.Column("yookassa_shop_id",    sa.String(64),  nullable=True))
    op.add_column("shop_settings", sa.Column("yookassa_secret_key", sa.String(256), nullable=True))
    op.add_column("shop_settings", sa.Column("yookassa_return_url", sa.String(512), nullable=True))


def downgrade() -> None:
    for col in ("yookassa_return_url", "yookassa_secret_key",
                "yookassa_shop_id", "yookassa_enabled"):
        op.drop_column("shop_settings", col)
