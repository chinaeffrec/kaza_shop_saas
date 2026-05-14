"""
Биллинговые модели платформы.

Plan      — тарифный план (free / basic / pro).
Subscription — активная подписка конкретного магазина на план.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# ── Константы тарифов (используются и в seed-данных миграции) ────────────────

PLAN_FREE  = "free"
PLAN_BASIC = "basic"
PLAN_PRO   = "pro"

PLAN_SLUGS = (PLAN_FREE, PLAN_BASIC, PLAN_PRO)

# Цены в копейках; -1 в лимитах означает «без ограничений»
PLAN_SEED: list[dict] = [
    {
        "slug": PLAN_FREE,
        "display_name": "Free",
        "price_monthly": 0,
        "max_products": 10,
        "max_orders_monthly": 50,
        "features": {"yookassa": False, "cdek": False, "miniapp": False},
        "is_public": True,
        "sort_order": 0,
    },
    {
        "slug": PLAN_BASIC,
        "display_name": "Basic",
        "price_monthly": 99000,        # 990 ₽
        "max_products": 100,
        "max_orders_monthly": 500,
        "features": {"yookassa": True, "cdek": False, "miniapp": False},
        "is_public": True,
        "sort_order": 1,
    },
    {
        "slug": PLAN_PRO,
        "display_name": "Pro",
        "price_monthly": 299000,       # 2 990 ₽
        "max_products": -1,
        "max_orders_monthly": -1,
        "features": {"yookassa": True, "cdek": True, "miniapp": True},
        "is_public": True,
        "sort_order": 2,
    },
]


class Plan(Base):
    """Тарифный план платформы."""

    __tablename__ = "plans"
    __table_args__ = (
        Index("ix_plans_slug", "slug", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    price_monthly: Mapped[int] = mapped_column(Integer, default=0)   # копейки
    max_products: Mapped[int] = mapped_column(Integer, default=10)    # -1 = ∞
    max_orders_monthly: Mapped[int] = mapped_column(Integer, default=50)  # -1 = ∞
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    # {"yookassa": bool, "cdek": bool, "miniapp": bool}
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="plan"
    )

    def __repr__(self) -> str:
        return f"<Plan {self.slug}>"


class Subscription(Base):
    """Подписка конкретного магазина на тарифный план."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscriptions_shop_id", "shop_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id"), nullable=False
    )
    # active | trialing | suspended | cancelled
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    plan: Mapped["Plan"] = relationship("Plan", back_populates="subscriptions")

    def __repr__(self) -> str:
        return f"<Subscription shop={self.shop_id} plan={self.plan_id} status={self.status}>"
