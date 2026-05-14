"""add product_variants table + variant fields to order_items

Revision ID: 20260513_0010
Revises: 20260513_0009
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = "20260513_0010"
down_revision = "20260513_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_variants",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_id", sa.Integer,
                  sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shop_id", sa.Integer,
                  sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sku", sa.String(100), nullable=True),
        sa.Column("price", sa.Integer, nullable=True),
        sa.Column("stock", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_unique_constraint(
        "uq_variant_shop_sku", "product_variants", ["shop_id", "sku"]
    )
    op.create_index("ix_product_variants_product_id", "product_variants", ["product_id"])
    op.create_index("ix_product_variants_shop_id", "product_variants", ["shop_id"])

    # Snapshot variant info on order items
    op.add_column("order_items",
        sa.Column("variant_id", sa.Integer,
                  sa.ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True))
    op.add_column("order_items",
        sa.Column("variant_name", sa.String(100), nullable=True))
    op.add_column("order_items",
        sa.Column("sku", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("order_items", "sku")
    op.drop_column("order_items", "variant_name")
    op.drop_column("order_items", "variant_id")
    op.drop_index("ix_product_variants_shop_id", table_name="product_variants")
    op.drop_index("ix_product_variants_product_id", table_name="product_variants")
    op.drop_constraint("uq_variant_shop_sku", "product_variants", type_="unique")
    op.drop_table("product_variants")
