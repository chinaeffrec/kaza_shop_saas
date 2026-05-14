from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
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

    # Profile extras
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # 2FA — TOTP (RFC 6238)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

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
    members: Mapped[List["ShopMember"]] = relationship(
        "ShopMember", back_populates="shop", cascade="all, delete-orphan",
        foreign_keys="ShopMember.shop_id",
    )

    def __repr__(self) -> str:
        return f"<Shop {self.name} [{self.status}]>"


class ShopMember(Base):
    """
    Участник команды магазина.

    Позволяет нескольким PlatformUser иметь доступ к одному магазину
    с разными ролями (owner, manager, support).

    owner_id на Shop остаётся для биллинга и юридической ответственности.
    ShopMember определяет права доступа в seller panel.
    """

    __tablename__ = "shop_members"
    __table_args__ = (
        UniqueConstraint("shop_id", "user_id", name="uq_shop_members_shop_user"),
        Index("ix_shop_members_shop_id", "shop_id"),
        Index("ix_shop_members_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("platform_users.id", ondelete="CASCADE"), nullable=False
    )
    # "owner" | "manager" | "support"
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="manager")
    invited_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("platform_users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    shop: Mapped["Shop"] = relationship(
        "Shop", back_populates="members", foreign_keys=[shop_id]
    )
    user: Mapped["PlatformUser"] = relationship(
        "PlatformUser", foreign_keys=[user_id]
    )
    invited_by: Mapped[Optional["PlatformUser"]] = relationship(
        "PlatformUser", foreign_keys=[invited_by_id]
    )

    def __repr__(self) -> str:
        return f"<ShopMember shop={self.shop_id} user={self.user_id} role={self.role}>"
