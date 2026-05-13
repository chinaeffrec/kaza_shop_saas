"""make shops.bot_token nullable

Магазин может существовать без бот-токена (токен добавляется позже
через PUT /platform/shops/{id}/bot-token).

Revision ID: 20260513_0005
Revises: 20260513_0004
Create Date: 2026-05-13 16:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260513_0005"
down_revision = "20260513_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "shops",
        "bot_token",
        existing_type=sa.String(512),
        nullable=True,
    )


def downgrade() -> None:
    # Обнуляем токены перед восстановлением NOT NULL, чтобы не падать
    # на строках с NULL (если таковые появились).
    op.execute("UPDATE shops SET bot_token = '' WHERE bot_token IS NULL")
    op.alter_column(
        "shops",
        "bot_token",
        existing_type=sa.String(512),
        nullable=False,
    )
