from __future__ import annotations

from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.product import Product


class SubCategory(Base):
    __tablename__ = "subcategories"
    __table_args__ = (
        Index("ix_subcategories_shop_id", "shop_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int | None] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE")
    )

    category: Mapped["Category"] = relationship("Category", back_populates="subcategories")
    products: Mapped[List["Product"]] = relationship(
        "Product", back_populates="subcategory", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SubCategory {self.name}>"
