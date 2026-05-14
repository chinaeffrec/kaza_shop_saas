"""Add missing performance indexes identified in security/load audit

Revision ID: 0024
Revises: 0023
Create Date: 2026-05-14

New indexes:
  orders.payment_id              — YooKassa webhook lookups (O(log n) instead of seq-scan)
  orders.cdek_order_uuid         — CDEK status polling lookups
  reviews.(shop_id, status)      — moderation queue: WHERE shop_id=X AND status='pending'
  products.(shop_id, is_active)  — catalog listing: WHERE shop_id=X AND is_active=true
  promo_codes.(code, shop_id)    — promo validation: WHERE code=X AND shop_id=Y
  platform_broadcasts.(is_active, expires_at) — active broadcasts query with expiry filter
"""
from alembic import op


def upgrade() -> None:
    # YooKassa: payment webhook → order lookup
    op.create_index(
        "ix_orders_payment_id",
        "orders",
        ["payment_id"],
        postgresql_where="payment_id IS NOT NULL",
    )

    # CDEK: status polling → order lookup
    op.create_index(
        "ix_orders_cdek_uuid",
        "orders",
        ["cdek_order_uuid"],
        postgresql_where="cdek_order_uuid IS NOT NULL",
    )

    # Reviews moderation queue (most common read pattern)
    op.create_index(
        "ix_reviews_shop_status",
        "reviews",
        ["shop_id", "status"],
    )

    # Catalog listing — compound replaces separate shop_id + is_active scans
    op.create_index(
        "ix_products_shop_active",
        "products",
        ["shop_id", "is_active"],
    )

    # Promo validation — composite so PG can use index-only scan
    op.create_index(
        "ix_promo_codes_code_shop",
        "promo_codes",
        ["code", "shop_id"],
    )

    # Active broadcasts with expiry filter
    op.create_index(
        "ix_broadcasts_active_expires",
        "platform_broadcasts",
        ["is_active", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_broadcasts_active_expires", table_name="platform_broadcasts")
    op.drop_index("ix_promo_codes_code_shop",     table_name="promo_codes")
    op.drop_index("ix_products_shop_active",      table_name="products")
    op.drop_index("ix_reviews_shop_status",       table_name="reviews")
    op.drop_index("ix_orders_cdek_uuid",          table_name="orders")
    op.drop_index("ix_orders_payment_id",         table_name="orders")
