from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductStats(Base):
    __tablename__ = "product_stats"

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), primary_key=True
    )
    added_to_cart: Mapped[int] = mapped_column(Integer, default=0)
    ordered: Mapped[int] = mapped_column(Integer, default=0)
    returned: Mapped[int] = mapped_column(Integer, default=0)
