from sqlalchemy import Boolean, Column, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ShopSettings(Base):
    __tablename__ = "shop_settings"
    __table_args__ = (
        Index("ix_shop_settings_shop_id", "shop_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int | None] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), nullable=True, unique=True
    )

    shop_name: Mapped[str] = mapped_column(String(128), default="Kaza Shop")
    logo_filename: Mapped[str | None] = mapped_column(String(256), nullable=True)
    reviews_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    hide_out_of_stock: Mapped[bool] = mapped_column(Boolean, default=False)
    welcome_message: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        default="👋 Добро пожаловать!\n\nВыберите действие:",
    )
    seller_contact: Mapped[str | None] = mapped_column(String(256), nullable=True)
    admin_contact: Mapped[str | None] = mapped_column(String(256), nullable=True)

    stamp_filename = Column(String, nullable=True)
    payment_qr_filename = Column(String, nullable=True)
    payment_qr_comment = Column(String, nullable=True)
    legal_name = Column(String, nullable=True)


class FaqItem(Base):
    __tablename__ = "faq_items"
    __table_args__ = (
        Index("ix_faq_items_shop_id", "shop_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int | None] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), nullable=True
    )
    question: Mapped[str] = mapped_column(String(512))
    answer: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
