from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

ORDER_STATUSES = {
    "new":       "🆕 Новый",
    "paid":      "💳 Оплачен",
    "confirmed": "✅ Подтверждён",
    "assembled": "📦 Собран",
    "shipped":   "🚚 Отправлен",
    "delivered": "✔️ Получен",
    "cancelled": "❌ Отменён",
    "returned":  "↩️ Возврат",
}


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_shop_id", "shop_id"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_user_id", "user_id"),
        Index("ix_orders_created_at", "created_at"),
        Index("ix_orders_shop_status_created", "shop_id", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int | None] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="new")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        Index("ix_order_items_order_id", "order_id"),
        Index("ix_order_items_product_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200))
    price: Mapped[int]
    quantity: Mapped[int] = mapped_column(default=1)

    order: Mapped["Order"] = relationship("Order", back_populates="items")
