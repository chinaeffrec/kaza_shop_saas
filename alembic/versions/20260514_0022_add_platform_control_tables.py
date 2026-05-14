"""add platform control tables: feature_flags, platform_broadcasts

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── feature_flags ─────────────────────────────────────────────────────────
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(128), nullable=False, unique=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_feature_flags_key", "feature_flags", ["key"], unique=True)

    # ── platform_broadcasts ───────────────────────────────────────────────────
    op.create_table(
        "platform_broadcasts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column(
            "created_by_id",
            sa.Integer,
            sa.ForeignKey("platform_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_by_email", sa.String(256), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_platform_broadcasts_is_active",
        "platform_broadcasts",
        ["is_active"],
    )

    # Seed three useful default feature flags
    op.execute("""
        INSERT INTO feature_flags (key, is_enabled, description, created_by)
        VALUES
            ('reviews_enabled',     true,  'Система отзывов покупателей',               'system'),
            ('miniapp_enabled',     true,  'Telegram Mini App для покупателей',          'system'),
            ('cdek_enabled',        false, 'Интеграция с CDEK для доставки',             'system')
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("platform_broadcasts")
    op.drop_table("feature_flags")
