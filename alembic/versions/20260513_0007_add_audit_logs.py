"""add audit_logs table

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        # Кто сделал действие
        sa.Column("actor_id", sa.Integer(), nullable=True),    # platform user id
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("actor_role", sa.String(50), nullable=True),
        # Контекст магазина (NULL = платформенное действие)
        sa.Column("shop_id", sa.Integer(), nullable=True),
        # Что произошло
        sa.Column("action", sa.String(100), nullable=False),    # e.g. "shop.status_changed"
        sa.Column("entity_type", sa.String(100), nullable=True), # e.g. "shop", "product"
        sa.Column("entity_id", sa.String(100), nullable=True),   # строка для гибкости
        # Детали изменения
        sa.Column("before_data", postgresql.JSONB(), nullable=True),
        sa.Column("after_data", postgresql.JSONB(), nullable=True),
        sa.Column("extra", postgresql.JSONB(), nullable=True),   # доп. контекст
        # Технические поля
        sa.Column("ip_address", sa.String(45), nullable=True),  # IPv4/IPv6
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Индексы для частых запросов
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_shop_id", "audit_logs", ["shop_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", "audit_logs")
    op.drop_index("ix_audit_logs_entity", "audit_logs")
    op.drop_index("ix_audit_logs_action", "audit_logs")
    op.drop_index("ix_audit_logs_shop_id", "audit_logs")
    op.drop_index("ix_audit_logs_actor_id", "audit_logs")
    op.drop_table("audit_logs")
