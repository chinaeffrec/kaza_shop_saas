"""extend bot_token column for encrypted storage

Fernet-зашифрованный токен длиннее исходного (~50 байт raw → ~120 байт
в base64url). String(512) гарантирует запас на любой размер ключа.

Revision ID: 20260513_0003
Revises: 20260513_0002
Create Date: 2026-05-13 14:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260513_0003"
down_revision = "20260513_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "shops",
        "bot_token",
        existing_type=sa.String(128),
        type_=sa.String(512),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "shops",
        "bot_token",
        existing_type=sa.String(512),
        type_=sa.String(128),
        existing_nullable=False,
    )
