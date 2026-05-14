"""add billing tables: plans, subscriptions

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-14
"""
import json
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

# Seed data for plans table
_PLANS = [
    {
        "slug": "free",
        "display_name": "Free",
        "price_monthly": 0,
        "max_products": 10,
        "max_orders_monthly": 50,
        "features": json.dumps({"yookassa": False, "cdek": False, "miniapp": False}),
        "is_public": True,
        "sort_order": 0,
    },
    {
        "slug": "basic",
        "display_name": "Basic",
        "price_monthly": 99000,
        "max_products": 100,
        "max_orders_monthly": 500,
        "features": json.dumps({"yookassa": True, "cdek": False, "miniapp": False}),
        "is_public": True,
        "sort_order": 1,
    },
    {
        "slug": "pro",
        "display_name": "Pro",
        "price_monthly": 299000,
        "max_products": -1,
        "max_orders_monthly": -1,
        "features": json.dumps({"yookassa": True, "cdek": True, "miniapp": True}),
        "is_public": True,
        "sort_order": 2,
    },
]


def upgrade() -> None:
    # ── plans ──────────────────────────────────────────────────────────────────
    op.create_table(
        "plans",
        sa.Column("id",                  sa.Integer(),     nullable=False),
        sa.Column("slug",                sa.String(32),    nullable=False),
        sa.Column("display_name",        sa.String(128),   nullable=False),
        sa.Column("price_monthly",       sa.Integer(),     nullable=False, server_default="0"),
        sa.Column("max_products",        sa.Integer(),     nullable=False, server_default="10"),
        sa.Column("max_orders_monthly",  sa.Integer(),     nullable=False, server_default="50"),
        sa.Column("features",            sa.JSON(),        nullable=True),
        sa.Column("is_public",           sa.Boolean(),     nullable=False, server_default="true"),
        sa.Column("sort_order",          sa.Integer(),     nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_plans_slug"),
    )
    op.create_index("ix_plans_slug", "plans", ["slug"], unique=True)

    # Seed plans
    plans_table = sa.table(
        "plans",
        sa.column("slug"),
        sa.column("display_name"),
        sa.column("price_monthly"),
        sa.column("max_products"),
        sa.column("max_orders_monthly"),
        sa.column("features"),
        sa.column("is_public"),
        sa.column("sort_order"),
    )
    op.bulk_insert(plans_table, _PLANS)

    # ── subscriptions ──────────────────────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id",             sa.Integer(),                            nullable=False),
        sa.Column("shop_id",        sa.Integer(),                            nullable=False),
        sa.Column("plan_id",        sa.Integer(),                            nullable=False),
        sa.Column("status",         sa.String(32),  server_default="active", nullable=False),
        sa.Column("started_at",     sa.DateTime(timezone=True),              nullable=True),
        sa.Column("expires_at",     sa.DateTime(timezone=True),              nullable=True),
        sa.Column("trial_ends_at",  sa.DateTime(timezone=True),              nullable=True),
        sa.Column("created_at",     sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",     sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shop_id", name="uq_subscriptions_shop_id"),
    )
    op.create_index("ix_subscriptions_shop_id", "subscriptions", ["shop_id"], unique=True)

    # Создать free-подписку для всех существующих магазинов
    op.execute("""
        INSERT INTO subscriptions (shop_id, plan_id, status, started_at, created_at, updated_at)
        SELECT
            s.id,
            p.id,
            'active',
            NOW(),
            NOW(),
            NOW()
        FROM shops s
        CROSS JOIN plans p
        WHERE p.slug = 'free'
          AND NOT EXISTS (
              SELECT 1 FROM subscriptions sub WHERE sub.shop_id = s.id
          )
    """)


def downgrade() -> None:
    op.drop_index("ix_subscriptions_shop_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_index("ix_plans_slug", table_name="plans")
    op.drop_table("plans")
