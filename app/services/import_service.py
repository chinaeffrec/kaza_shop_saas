"""Сервис импорта товаров из Excel."""
import logging
from io import BytesIO

import pandas as pd
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.stats import ImportResponse
from app.models.category import Category
from app.models.product import Product
from app.models.subcategory import SubCategory
from app.services.cache_service import invalidate_catalog_cache

logger = logging.getLogger(__name__)
MAX_IMPORT_SIZE = 20 * 1024 * 1024


async def _get_or_create_category(
    session: AsyncSession, name: str, shop_id: int
) -> Category:
    name = name.strip()
    res = await session.execute(
        select(Category).where(Category.name == name, Category.shop_id == shop_id)
    )
    cat = res.scalar_one_or_none()
    if not cat:
        cat = Category(name=name, shop_id=shop_id)
        session.add(cat)
        await session.flush()
    return cat


async def _get_or_create_subcategory(
    session: AsyncSession, cat_id: int, name: str, shop_id: int
) -> SubCategory:
    name = name.strip()
    res = await session.execute(
        select(SubCategory).where(
            SubCategory.name == name,
            SubCategory.category_id == cat_id,
            SubCategory.shop_id == shop_id,
        )
    )
    sub = res.scalar_one_or_none()
    if not sub:
        sub = SubCategory(name=name, category_id=cat_id, shop_id=shop_id)
        session.add(sub)
        await session.flush()
    return sub


async def import_products(
    content: bytes, session: AsyncSession, shop_id: int = 1
) -> ImportResponse:
    if len(content) > MAX_IMPORT_SIZE:
        raise HTTPException(413, f"File too large. Max {MAX_IMPORT_SIZE // 1024 // 1024} MB.")
    try:
        df = pd.read_excel(BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Error reading Excel: {e}")

    required = {"category", "subcategory", "name", "price"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(400, f"Missing columns: {missing}")

    created = updated = 0
    errors: list[str] = []

    try:
        for idx, row in df.iterrows():
            try:
                name = str(row["name"]).strip()
                if not name or name == "nan":
                    continue

                cat = await _get_or_create_category(session, str(row["category"]), shop_id)
                sub = await _get_or_create_subcategory(session, cat.id, str(row["subcategory"]), shop_id)

                price = int(float(row["price"]))

                def _opt_int(col):
                    if col in df.columns and not pd.isna(row.get(col)):
                        try:
                            return int(float(row[col]))
                        except Exception:
                            pass
                    return None

                def _opt_str(col):
                    if col in df.columns and not pd.isna(row.get(col)):
                        v = str(row[col]).strip()
                        return v if v else None
                    return None

                def _opt_bool(col, default=True):
                    if col in df.columns and not pd.isna(row.get(col)):
                        val = row[col]
                        if isinstance(val, bool):
                            return val
                        return str(val).strip().lower() not in ("false", "0", "нет", "no")
                    return default

                res = await session.execute(
                    select(Product).where(
                        Product.name == name,
                        Product.subcategory_id == sub.id,
                        Product.shop_id == shop_id,
                    )
                )
                existing = res.scalar_one_or_none()

                kwargs = dict(
                    price=price,
                    discount_price=_opt_int("discount_price"),
                    description=_opt_str("description"),
                    characteristics=_opt_str("characteristics"),
                    is_active=_opt_bool("is_active"),
                    stock=_opt_int("stock") or 0,
                )
                if existing:
                    for k, v in kwargs.items():
                        setattr(existing, k, v)
                    updated += 1
                else:
                    session.add(Product(
                        subcategory_id=sub.id, name=name, shop_id=shop_id, **kwargs
                    ))
                    created += 1

            except Exception as e:
                errors.append(f"Row {idx} ({row.get('name', '?')}): {e}")

        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(500, f"Import failed: {e}")

    await invalidate_catalog_cache(shop_id)
    return ImportResponse(status="ok", created=created, updated=updated, errors=errors)
