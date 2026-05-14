"""add reviews table

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id",          sa.Integer(),                          nullable=False),
        sa.Column("shop_id",     sa.Integer(),                          nullable=False),
        sa.Column("product_id",  sa.Integer(),                          nullable=False),
        sa.Column("user_id",     sa.BigInteger(),                       nullable=False),
        sa.Column("order_id",    sa.Integer(),                          nullable=True),
        sa.Column("rating",      sa.SmallInteger(),                     nullable=False),
        sa.Column("text",        sa.Text(),                             nullable=True),
        sa.Column("is_approved", sa.Boolean(), server_default="false",  nullable=False),
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",  sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"],    ["shops.id"],    ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"],   ["orders.id"],   ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "order_id", name="uq_reviews_user_order"),
    )
    op.create_index("ix_reviews_shop_id",    "reviews", ["shop_id"])
    op.create_index("ix_reviews_product_id", "reviews", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_reviews_product_id", table_name="reviews")
    op.drop_index("ix_reviews_shop_id",    table_name="reviews")
    op.drop_table("reviews")
