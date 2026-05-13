import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx

from app.bot.services.api_auth import bot_headers

BASE_URL = "http://app:8000"
logger = logging.getLogger(__name__)


@dataclass
class Product:
    id: int
    name: str
    price: int
    discount_price: Optional[int]
    description: Optional[str]
    characteristics: Optional[str]
    image: Optional[str]
    images: list
    image_url: Optional[str]
    image_url_2: Optional[str]
    image_url_3: Optional[str]
    subcategory_id: int


@dataclass
class SubCategory:
    id: int
    name: str
    category_id: int
    products: List[Product] = field(default_factory=list)


@dataclass
class Category:
    id: int
    name: str
    subcategories: List[SubCategory] = field(default_factory=list)


class CatalogCache:
    def __init__(self, shop_id: int = 1):
        self.shop_id = shop_id
        self.categories: Dict[int, Category] = {}

    async def _wait_for_app(self):
        for attempt in range(15):
            try:
                async with httpx.AsyncClient(timeout=3) as client:
                    r = await client.get(f"{BASE_URL}/health")
                    if r.status_code == 200:
                        logger.info("App is ready (shop_id=%s)", self.shop_id)
                        return
            except Exception:
                pass
            logger.info("Waiting for app... (%s/15, shop_id=%s)", attempt + 1, self.shop_id)
            await asyncio.sleep(2)
        logger.warning("Proceeding anyway (shop_id=%s)", self.shop_id)

    async def load(self):
        await self._wait_for_app()
        self.categories = {}
        hdrs = bot_headers(shop_id=self.shop_id)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                cat_res = await client.get(f"{BASE_URL}/catalog/categories", headers=hdrs)
                categories_data = cat_res.json()

                if not isinstance(categories_data, list):
                    logger.warning("Bad response (shop_id=%s): %s", self.shop_id, categories_data)
                    return

                for c in categories_data:
                    if not isinstance(c, dict):
                        continue

                    sub_res = await client.get(
                        f"{BASE_URL}/catalog/categories/{c['id']}/subcategories",
                        headers=hdrs,
                    )
                    subs_data = sub_res.json()
                    if not isinstance(subs_data, list):
                        continue

                    sub_list = []
                    for s in subs_data:
                        if not isinstance(s, dict):
                            continue

                        prod_res = await client.get(
                            f"{BASE_URL}/catalog/subcategories/{s['id']}/products",
                            headers=hdrs,
                        )
                        products_data = prod_res.json()

                        products = [
                            Product(
                                id=p["id"],
                                name=p["name"],
                                price=p["price"],
                                discount_price=p.get("discount_price"),
                                description=p.get("description"),
                                characteristics=p.get("characteristics"),
                                image=p.get("image_file_id"),
                                images=p.get("images", []),
                                image_url=p.get("image_url"),
                                image_url_2=p.get("image_url_2"),
                                image_url_3=p.get("image_url_3"),
                                subcategory_id=s["id"],
                            )
                            for p in (products_data if isinstance(products_data, list) else [])
                        ]

                        sub_list.append(SubCategory(
                            id=s["id"],
                            name=s["name"],
                            category_id=c["id"],
                            products=products,
                        ))

                    self.categories[c["id"]] = Category(
                        id=c["id"],
                        name=c["name"],
                        subcategories=sub_list,
                    )

            logger.info("Loaded %s categories (shop_id=%s)", len(self.categories), self.shop_id)

        except Exception as e:
            logger.exception("Load failed (shop_id=%s): %s", self.shop_id, e)

    def get_categories(self) -> List[Category]:
        return list(self.categories.values())

    def get_visible_categories(self) -> List[Category]:
        result = []
        for cat in self.categories.values():
            visible_subs = [s for s in cat.subcategories if s.products]
            if visible_subs:
                result.append(Category(
                    id=cat.id,
                    name=cat.name,
                    subcategories=visible_subs,
                ))
        return result

    def get_category(self, category_id: int) -> Optional[Category]:
        return self.categories.get(category_id)

    def get_subcategory_by_id(self, sub_id: int) -> Optional[SubCategory]:
        for cat in self.categories.values():
            for sub in cat.subcategories:
                if sub.id == sub_id:
                    return sub
        return None

    def get_product(self, product_id: int) -> Optional[Product]:
        for cat in self.categories.values():
            for sub in cat.subcategories:
                for p in sub.products:
                    if p.id == product_id:
                        return p
        return None


# Legacy singleton for backward compatibility (single-bot mode, shop_id=1)
catalog_cache = CatalogCache(shop_id=1)
