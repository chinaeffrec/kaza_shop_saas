from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    """Telegram-пользователь в контексте конкретного магазина.

    id           — суррогатный PK (autoincrement)
    telegram_id  — Telegram user ID (был PK до Phase 3)
    shop_id      — FK на магазин; один Telegram-пользователь может быть
                   зарегистрирован в нескольких магазинах как разные строки
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("telegram_id", "shop_id", name="uq_user_telegram_shop"),
        Index("ix_users_telegram_id", "telegram_id"),
        Index("ix_users_shop_id", "shop_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shop_id: Mapped[int | None] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), nullable=True
    )

    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<User tg={self.telegram_id} shop={self.shop_id}>"
