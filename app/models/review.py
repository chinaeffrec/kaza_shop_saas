"""Модель отзыва покупателя."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey,
    Index, Integer, SmallInteger, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Review(Base):
    """Отзыв покупателя о товаре в рамках конкретного заказа."""

    __tablename__ = "reviews"
    __table_args__ = (
        # Один отзыв на заказ — запрещает дублирование
        UniqueConstraint("user_id", "order_id", name="uq_reviews_user_order"),
        Index("ix_reviews_shop_id",    "shop_id"),
        Index("ix_reviews_product_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # FK-ссылки
    shop_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    # Telegram user_id (BigInteger — может быть > 2^31)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    order_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )

    # Контент
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)   # 1–5
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Модерация: False = ожидает, True = одобрен
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships (lazy — не грузим лишнее)
    product: Mapped["Product"] = relationship(  # type: ignore[name-defined]
        "Product", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Review id={self.id} order={self.order_id} rating={self.rating}>"
