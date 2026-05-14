"""add language field to users

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column(
        "language", sa.String(8), nullable=False, server_default="ru"
    ))


def downgrade() -> None:
    op.drop_column("users", "language")
