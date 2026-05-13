"""add platform_users and shops

Revision ID: 20260513_0002
Revises: 20260509_0001
Create Date: 2026-05-13 14:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260513_0002"
down_revision = "20260509_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(256), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("is_super_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.execute("CREATE UNIQUE INDEX ix_platform_users_email ON platform_users (email)")

    op.create_table(
        "shops",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("platform_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("bot_token", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="trial"),
        sa.Column("plan", sa.String(32), nullable=False, server_default="trial"),
        sa.Column("plan_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_products", sa.Integer(), nullable=False, server_default="50"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.execute("CREATE INDEX ix_shops_owner_id ON shops (owner_id)")
    op.execute("CREATE INDEX ix_shops_status ON shops (status)")


def downgrade() -> None:
    op.drop_table("shops")
    op.drop_table("platform_users")
