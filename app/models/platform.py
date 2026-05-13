from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    pass

SHOP_STATUSES = ("trial", "active", "suspended")
SHOP_PLANS = ("trial", "basic", "pro")

PLAN_MAX_PRODUCTS = {
    "trial": 50,
    "basic": 1000,
    "pro": 0,  # 0 = без лимита
}


class PlatformUser(Base):
    """Владелец магазина или суперадмин платформы."""

    __tablename__ = "platform_users"
    __table_args__ = (
        Index("ix_platform_users_email", "email", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    shops: Mapped[List["Shop"]] = relationship("Shop", back_populates="owner")

    def __repr__(self) -> str:
        return f"<PlatformUser {self.email}>"


class Shop(Base):
    """Экземпляр магазина, привязанный к владельцу."""

    __tablename__ = "shops"
    __table_args__ = (
        Index("ix_shops_owner_id", "owner_id"),
        Index("ix_shops_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("platform_users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    # Fernet-encrypted; nullable — новый магазин может не иметь токена сразу
    bot_token: Mapped[str | None] = mapped_column(String(512), nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="trial")
    plan: Mapped[str] = mapped_column(String(32), default="trial")
    plan_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    max_products: Mapped[int] = mapped_column(
        Integer, default=PLAN_MAX_PRODUCTS["trial"]
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    owner: Mapped["PlatformUser"] = relationship("PlatformUser", back_populates="shops")

    def __repr__(self) -> str:
        return f"<Shop {self.name} [{self.status}]>"
