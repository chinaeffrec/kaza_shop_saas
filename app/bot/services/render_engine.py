import logging

import httpx

from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from app.bot.keyboards.catalog import categories_kb, subcategories_kb
from app.bot.services.api_auth import bot_headers
from app.bot.services.catalog_cache import CatalogCache, catalog_cache as _default_cache

logger = logging.getLogger(__name__)


def _fmt_price(price) -> str:
    if price is None:
        return "—"
    try:
        price = float(price)
    except (TypeError, ValueError):
        return str(price)
    if price != int(price):
        whole = int(price)
        frac_str = f"{price:.2f}"[len(str(whole)):]
        whole_str = f"{whole:,}".replace(",", " ")
        return f"{whole_str}{frac_str} ₽"
    return f"{int(price):,}".replace(",", " ") + " ₽"


def _product_kb(product, idx: int, total: int, products: list, photo_idx: int = 0) -> InlineKeyboardMarkup:
    image_urls = [u for u in [getattr(product, "image_url", None),
                              getattr(product, "image_url_2", None),
                              getattr(product, "image_url_3", None)] if u]
    rows = []

    if len(image_urls) > 1:
        prev_pi = (photo_idx - 1) % len(image_urls)
        next_pi = (photo_idx + 1) % len(image_urls)
        rows.append([
            InlineKeyboardButton(text="◀️ Фото", callback_data=f"photo_{product.id}_{prev_pi}"),
            InlineKeyboardButton(text=f"📷 {photo_idx+1}/{len(image_urls)}", callback_data="noop"),
            InlineKeyboardButton(text="Фото ▶️", callback_data=f"photo_{product.id}_{next_pi}"),
        ])

    nav_row = []
    if idx > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"open_product_{products[idx-1].id}"))
    nav_row.append(InlineKeyboardButton(text=f"📦 {idx+1}/{total}", callback_data="noop"))
    if idx < total - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"open_product_{products[idx+1].id}"))
    rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="🛒 В корзину", callback_data=f"cart_add_{product.id}")])
    rows.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="menu_back"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _generate_placeholder_image(product, shop_id: int = 1) -> bytes:
    import io
    from PIL import Image, ImageDraw, ImageFont

    shop_title = "Kaza Shop"
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get(
                "http://app:8000/settings/public",
                headers=bot_headers(shop_id=shop_id),
            )
            if r.status_code == 200:
                shop_title = r.json().get("shop_name", "Kaza Shop")
    except Exception:
        pass

    W, H = 500, 400
    img = Image.new('RGB', (W, H), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W - 1, H - 1], outline=(220, 220, 230), width=2)
    draw.rectangle([0, 0, W, 60], fill=(108, 99, 255))

    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        font_price = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
        font_body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except Exception:
        font_title = font_price = font_body = ImageFont.load_default()

    shop_display = shop_title[:30] + ("..." if len(shop_title) > 30 else "")
    draw.text((20, 15), shop_display, fill=(255, 255, 255), font=font_title)
    draw.ellipse([W//2 - 40, 100, W//2 + 40, 180], outline=(200, 200, 210), width=3)
    draw.line([W//2 - 20, 140, W//2 + 20, 140], fill=(200, 200, 210), width=3)
    draw.line([W//2, 120, W//2, 160], fill=(200, 200, 210), width=3)

    name = product.name[:35] + ("..." if len(product.name) > 35 else "")
    draw.text((30, 210), name, fill=(40, 40, 60), font=font_title)

    price_text = f"{product.price:,} ₽".replace(",", " ")
    bbox = draw.textbbox((0, 0), price_text, font=font_price)
    price_w = bbox[2] - bbox[0]
    draw.text((W - price_w - 30, 260), price_text, fill=(108, 99, 255), font=font_price)

    if product.description:
        desc = product.description[:60] + ("..." if len(product.description or "") > 60 else "")
        draw.text((30, 310), desc, fill=(150, 150, 160), font=font_body)

    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=90)
    return buf.getvalue()


async def render_product_card(
    message: Message,
    product,
    idx: int,
    total: int,
    photo_idx: int = 0,
    *,
    cache: CatalogCache | None = None,
    shop_id: int = 1,
):
    cache = cache or _default_cache
    sub = cache.get_subcategory_by_id(product.subcategory_id)
    products = sub.products if sub else [product]
    kb = _product_kb(product, idx, total, products, photo_idx)
    caption = _product_caption(product)

    image_urls = [u for u in [getattr(product, "image_url", None),
                              getattr(product, "image_url_2", None),
                              getattr(product, "image_url_3", None)] if u]

    photo_content = None
    filename = "product.jpg"

    if image_urls:
        url = image_urls[photo_idx % len(image_urls)]
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(f"http://app:8000{url}")
                if resp.status_code == 200:
                    photo_content = resp.content
                    filename = url.split("/")[-1]
            except Exception as e:
                logger.warning("Failed to download photo %s: %s", url, e)

    if not photo_content:
        try:
            photo_content = await _generate_placeholder_image(product, shop_id)
            filename = "placeholder.jpg"
        except Exception as e:
            logger.warning("Placeholder generation failed: %s", e)
            await _safe_edit_text(message, caption, kb)
            return

    try:
        photo = BufferedInputFile(photo_content, filename=filename)
        if message.photo:
            await message.edit_media(
                media=InputMediaPhoto(media=photo, caption=caption, parse_mode="HTML"),
                reply_markup=kb,
            )
        else:
            try:
                await message.delete()
            except Exception:
                pass
            await message.answer_photo(
                photo=photo, caption=caption, reply_markup=kb, parse_mode="HTML",
            )
    except Exception as e:
        logger.warning("Photo send error for product %s: %s", product.id, e)
        await _safe_edit_text(message, caption, kb)


def _product_caption(product) -> str:
    lines = [f"<b>{product.name}</b>"]
    if getattr(product, "discount_price", None):
        lines.append(f"💰 <s>{_fmt_price(product.price)}</s> → <b>{_fmt_price(product.discount_price)}</b>")
    else:
        lines.append(f"💰 <b>{_fmt_price(product.price)}</b>")
    if product.characteristics:
        lines.append(f"\n📋 {product.characteristics}")
    if product.description:
        lines.append(f"\n{product.description}")
    return "\n".join(lines)


async def _render_text(message: Message, text: str, kb: InlineKeyboardMarkup):
    if message.photo or message.document:
        try:
            await message.delete()
        except Exception:
            pass
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await _safe_edit_text(message, text, kb)


async def _safe_edit_text(message: Message, text: str, kb: InlineKeyboardMarkup):
    try:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        try:
            await message.answer(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass


class RenderEngine:
    async def render(
        self,
        screen,
        message: Message,
        *,
        cache: CatalogCache | None = None,
        shop_id: int = 1,
    ):
        cache = cache or _default_cache

        if screen.type == "categories":
            categories = cache.get_visible_categories()
            if not categories:
                await _render_text(
                    message,
                    "🗂 <b>Каталог</b>\n\nНет доступных товаров.",
                    InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="🏠 В меню", callback_data="menu_back")
                    ]]),
                )
                return
            await _render_text(message, "🗂 <b>Каталог</b>\n\nВыберите категорию:", categories_kb(categories))

        elif screen.type == "subcategories":
            category = cache.get_category(screen.category_id)
            if not category:
                await _render_text(
                    message,
                    "Категория не найдена",
                    InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="⬅️ Назад", callback_data="back")
                    ]]),
                )
                return
            await _render_text(
                message,
                f"📁 <b>{category.name}</b>\n\nВыберите подкатегорию:",
                subcategories_kb(category.subcategories),
            )

        elif screen.type in ("products", "product"):
            if screen.type == "products":
                sub = cache.get_subcategory_by_id(screen.subcategory_id)
                if not sub or not sub.products:
                    name = getattr(sub, "name", "Подкатегория") if sub else "Подкатегория"
                    await _render_text(
                        message,
                        f"📁 <b>{name}</b>\n\nТоваров нет.",
                        InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text="⬅️ Назад", callback_data="back")
                        ]]),
                    )
                    return
                product = sub.products[0]
                idx = 0
                total = len(sub.products)
            else:
                product = cache.get_product(screen.product_id)
                if not product:
                    await _render_text(
                        message,
                        "Товар не найден",
                        InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text="⬅️ Назад", callback_data="back")
                        ]]),
                    )
                    return
                sub = cache.get_subcategory_by_id(product.subcategory_id)
                products_list = sub.products if sub else [product]
                idx = next((i for i, p in enumerate(products_list) if p.id == product.id), 0)
                total = len(products_list)

            await render_product_card(message, product, idx, total, cache=cache, shop_id=shop_id)

        elif screen.type == "cart":
            from app.bot.handlers.menu import build_cart_keyboard, build_cart_text
            user_id = message.chat.id
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(
                        f"http://app:8000/cart/{user_id}",
                        headers=bot_headers(user_id, shop_id),
                    )
                data = response.json()
            except Exception as e:
                logger.warning("Cart fetch failed for user %s: %s", user_id, e)
                await _render_text(
                    message,
                    "🛒 Не удалось загрузить корзину. Попробуйте позже.",
                    InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")
                    ]]),
                )
                return
            if not data.get("items"):
                await _render_text(
                    message,
                    "🛒 Ваша корзина пуста",
                    InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")
                    ]]),
                )
            else:
                await _safe_edit_text(message, build_cart_text(data), build_cart_keyboard(data))


render_engine = RenderEngine()
