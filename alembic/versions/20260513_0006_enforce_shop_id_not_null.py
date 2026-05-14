"""enforce NOT NULL on all tenant shop_id columns

Phase 7: backfill NULL → 1 (legacy single-tenant shop), then set NOT NULL.
All shop_id FK columns were added as nullable in 0004 to allow zero-downtime
deployment of existing single-tenant data. This migration finalises the
multi-tenant schema enforcement.

Tables affected:
  categories, subcategories, products, shop_settings, faq_items,
  users, carts, orders

Revision ID: 20260513_0006
Revises: 20260513_0005
Create Date: 2026-05-13 17:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260513_0006"
down_revision = "20260513_0005"
branch_labels = None
depends_on = None

# Tables whose shop_id column just needs backfill + NOT NULL.
_SIMPLE_TABLES = [
    "categories",
    "subcategories",
    "products",
    "shop_settings",
    "faq_items",
    "users",
    "carts",
    "orders",
]


def upgrade() -> None:
    # Ensure the legacy shop (id=1) exists before backfilling FKs.
    # If no shops exist at all (fresh install), skip the backfill gracefully.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM shops WHERE id = 1) THEN
                UPDATE categories    SET shop_id = 1 WHERE shop_id IS NULL;
                UPDATE subcategories SET shop_id = 1 WHERE shop_id IS NULL;
                UPDATE products      SET shop_id = 1 WHERE shop_id IS NULL;
                UPDATE shop_settings SET shop_id = 1 WHERE shop_id IS NULL;
                UPDATE faq_items     SET shop_id = 1 WHERE shop_id IS NULL;
                UPDATE users         SET shop_id = 1 WHERE shop_id IS NULL;
                UPDATE carts         SET shop_id = 1 WHERE shop_id IS NULL;
                UPDATE orders        SET shop_id = 1 WHERE shop_id IS NULL;
            END IF;
        END
        $$;
    """)

    for table in _SIMPLE_TABLES:
        op.alter_column(
            table,
            "shop_id",
            existing_type=sa.Integer(),
            nullable=False,
        )


def downgrade() -> None:
    for table in reversed(_SIMPLE_TABLES):
        op.alter_column(
            table,
            "shop_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
