from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProductVariant(Base):
    """
    Вариант товара (размер, цвет, комплектация и т.п.).

    Если у товара есть хотя бы один активный вариант, покупатель
    обязан выбрать вариант перед добавлением в корзину.

    price: абсолютная цена варианта; если None — используется цена родительского товара.
    sku:   артикул, уникальный в рамках магазина.
    """

    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("shop_id", "sku", name="uq_variant_shop_sku"),
        Index("ix_product_variants_product_id", "product_id"),
        Index("ix_product_variants_shop_id", "shop_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)          # "L", "Красный", "Pro"
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)     # может отсутствовать
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)       # None → цена из product
    stock: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    product: Mapped["Product"] = relationship("Product", back_populates="variants")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<ProductVariant {self.name} sku={self.sku} stock={self.stock}>"
