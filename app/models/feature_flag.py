"""
Platform-level control models.

FeatureFlag      — runtime feature toggles без деплоя.
PlatformBroadcast — системные сообщения от суперадмина всем владельцам.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FeatureFlag(Base):
    """Runtime feature toggle. Хранится в БД, читается на лету."""

    __tablename__ = "feature_flags"
    __table_args__ = (
        Index("ix_feature_flags_key", "key", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<FeatureFlag {self.key}={'on' if self.is_enabled else 'off'}>"


class PlatformBroadcast(Base):
    """Системное сообщение суперадмина — отображается в seller panel всем владельцам."""

    __tablename__ = "platform_broadcasts"
    __table_args__ = (
        Index("ix_platform_broadcasts_is_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("platform_users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<PlatformBroadcast #{self.id} '{self.title}'>"
