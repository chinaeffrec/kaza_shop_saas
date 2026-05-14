from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ShopSettings(Base):
    __tablename__ = "shop_settings"
    __table_args__ = (
        Index("ix_shop_settings_shop_id", "shop_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, unique=True
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

    # ── YooKassa ──────────────────────────────────────────────────────────────
    yookassa_enabled = Column(Boolean, nullable=False, default=False, server_default="false")
    yookassa_shop_id = Column(String(64), nullable=True)     # числовой ID магазина ЮКасса
    yookassa_secret_key = Column(String(256), nullable=True)  # secret_key (test_ или live_)
    yookassa_return_url = Column(String(512), nullable=True)  # URL после оплаты (сайт/бот)

    # ── i18n ──────────────────────────────────────────────────────────────────
    default_language = Column(String(8), nullable=False, default="ru", server_default="ru")
    # Список включённых языков через запятую: "ru,en,kk"
    shop_languages = Column(String(64), nullable=False, default="ru", server_default="ru")

    # ── Mini App ──────────────────────────────────────────────────────────────
    miniapp_url = Column(String(512), nullable=True)  # HTTPS URL Mini App (для WebApp-кнопки в боте)

    # ── CDEK ──────────────────────────────────────────────────────────────────
    cdek_enabled = Column(Boolean, nullable=False, default=False, server_default="false")
    cdek_test_mode = Column(Boolean, nullable=False, default=True, server_default="true")
    cdek_client_id = Column(String(128), nullable=True)
    cdek_client_secret = Column(String(256), nullable=True)
    cdek_sender_city_code = Column(Integer, nullable=True)   # CDEK city code (e.g. 44 = Москва)
    cdek_sender_address = Column(String(512), nullable=True) # адрес отправки
    cdek_default_weight = Column(Integer, nullable=False, default=500, server_default="500")  # г


class FaqItem(Base):
    __tablename__ = "faq_items"
    __table_args__ = (
        Index("ix_faq_items_shop_id", "shop_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(String(512))
    answer: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
