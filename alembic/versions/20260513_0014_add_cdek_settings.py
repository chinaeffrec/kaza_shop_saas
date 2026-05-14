"""add CDEK fields to shop_settings

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shop_settings", sa.Column("cdek_enabled",          sa.Boolean,     nullable=False, server_default="false"))
    op.add_column("shop_settings", sa.Column("cdek_test_mode",        sa.Boolean,     nullable=False, server_default="true"))
    op.add_column("shop_settings", sa.Column("cdek_client_id",        sa.String(128), nullable=True))
    op.add_column("shop_settings", sa.Column("cdek_client_secret",    sa.String(256), nullable=True))
    op.add_column("shop_settings", sa.Column("cdek_sender_city_code", sa.Integer,     nullable=True))
    op.add_column("shop_settings", sa.Column("cdek_sender_address",   sa.String(512), nullable=True))
    op.add_column("shop_settings", sa.Column("cdek_default_weight",   sa.Integer,     nullable=False, server_default="500"))


def downgrade() -> None:
    for col in ("cdek_default_weight", "cdek_sender_address", "cdek_sender_city_code",
                "cdek_client_secret", "cdek_client_id", "cdek_test_mode", "cdek_enabled"):
        op.drop_column("shop_settings", col)
