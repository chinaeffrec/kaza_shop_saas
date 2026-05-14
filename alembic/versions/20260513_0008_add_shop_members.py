"""add shop_members table

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-13

Создаёт таблицу shop_members для team access.
Сидирует: каждый существующий shop.owner_id → shop_members(role='owner').
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="manager"),
        sa.Column("invited_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["platform_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_id"], ["platform_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shop_id", "user_id", name="uq_shop_members_shop_user"),
    )
    op.create_index("ix_shop_members_shop_id", "shop_members", ["shop_id"])
    op.create_index("ix_shop_members_user_id", "shop_members", ["user_id"])

    # Сид: переносим owner_id → shop_members с ролью 'owner'
    # Используем INSERT ... ON CONFLICT DO NOTHING на случай повторного запуска
    op.execute("""
        INSERT INTO shop_members (shop_id, user_id, role)
        SELECT s.id, s.owner_id, 'owner'
        FROM shops s
        WHERE s.owner_id IS NOT NULL
        ON CONFLICT (shop_id, user_id) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("ix_shop_members_user_id", "shop_members")
    op.drop_index("ix_shop_members_shop_id", "shop_members")
    op.drop_table("shop_members")
