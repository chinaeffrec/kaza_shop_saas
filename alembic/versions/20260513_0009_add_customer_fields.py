"""add customer fields (phone, notes) to users + staff_notes to orders

Revision ID: 20260513_0009
Revises: 20260513_0008
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = "20260513_0009"
down_revision = "20260513_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # CRM fields on users
    op.add_column("users", sa.Column("phone", sa.String(32), nullable=True))
    op.add_column("users", sa.Column("notes", sa.Text, nullable=True))

    # Internal staff notes on orders (separate from customer comment)
    op.add_column("orders", sa.Column("staff_notes", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "staff_notes")
    op.drop_column("users", "notes")
    op.drop_column("users", "phone")
