"""add promo_codes table

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "promo_codes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("shop_id", sa.Integer, sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("discount_type", sa.String(10), nullable=False),
        sa.Column("value", sa.Integer, nullable=False),
        sa.Column("min_order_amount", sa.Integer, nullable=True),
        sa.Column("max_uses", sa.Integer, nullable=True),
        sa.Column("used_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_unique_constraint("uq_promo_shop_code", "promo_codes", ["shop_id", "code"])
    op.create_index("ix_promo_codes_shop_id", "promo_codes", ["shop_id"])


def downgrade() -> None:
    op.drop_index("ix_promo_codes_shop_id", "promo_codes")
    op.drop_table("promo_codes")
