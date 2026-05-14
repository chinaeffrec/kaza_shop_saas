"""
RBAC — Role-Based Access Control.

Роли платформы:
  super_admin  — полный доступ ко всему
  owner        — полный доступ к своему магазину + управление командой
  manager      — работа с товарами, заказами, контентом; без деструктивных операций
  support      — только просмотр и обработка заказов

Permissions используются как строки вида "ресурс:действие".
super_admin имеет wildcard "*" — имеет все права без явного перечисления.

Использование в роутах:
    from app.core.rbac import Perm
    from app.api.deps import require_permission

    @router.get("/products")
    async def list_products(ctx = require_permission(Perm.PRODUCTS_READ)):
        ...
"""
from __future__ import annotations

# ── Роли ──────────────────────────────────────────────────────────────────────

ROLE_SUPER_ADMIN = "super_admin"
ROLE_OWNER = "owner"
ROLE_MANAGER = "manager"
ROLE_SUPPORT = "support"

# Роли, которые могут быть назначены участникам магазина (не суперадмин)
SHOP_ROLES = (ROLE_OWNER, ROLE_MANAGER, ROLE_SUPPORT)


# ── Права ─────────────────────────────────────────────────────────────────────

class Perm:
    """Константы прав доступа."""

    # Каталог
    CATALOG_READ = "catalog:read"

    # Товары
    PRODUCTS_READ = "products:read"
    PRODUCTS_WRITE = "products:write"

    # Заказы
    ORDERS_READ = "orders:read"
    ORDERS_WRITE = "orders:write"

    # Статистика
    STATS_READ = "stats:read"
    STATS_EXPORT = "stats:export"

    # Настройки
    SETTINGS_READ = "settings:read"
    SETTINGS_WRITE = "settings:write"
    SETTINGS_DESTRUCTIVE = "settings:destructive"   # импорт БД/медиа

    # FAQ
    FAQ_READ = "faq:read"
    FAQ_WRITE = "faq:write"

    # Импорт товаров
    IMPORT_WRITE = "import:write"

    # Команда магазина
    MEMBERS_READ = "members:read"
    MEMBERS_WRITE = "members:write"

    # Промокоды / скидки
    PROMOS_READ = "promos:read"
    PROMOS_WRITE = "promos:write"

    # Отзывы покупателей
    REVIEWS_READ = "reviews:read"
    REVIEWS_WRITE = "reviews:write"

    # Платформенный доступ (только super_admin)
    PLATFORM_ADMIN = "platform:admin"


# ── Маппинг роль → права ──────────────────────────────────────────────────────

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    ROLE_SUPER_ADMIN: frozenset(["*"]),

    ROLE_OWNER: frozenset([
        Perm.CATALOG_READ,
        Perm.PRODUCTS_READ, Perm.PRODUCTS_WRITE,
        Perm.ORDERS_READ, Perm.ORDERS_WRITE,
        Perm.STATS_READ, Perm.STATS_EXPORT,
        Perm.SETTINGS_READ, Perm.SETTINGS_WRITE, Perm.SETTINGS_DESTRUCTIVE,
        Perm.FAQ_READ, Perm.FAQ_WRITE,
        Perm.IMPORT_WRITE,
        Perm.MEMBERS_READ, Perm.MEMBERS_WRITE,
        Perm.PROMOS_READ, Perm.PROMOS_WRITE,
        Perm.REVIEWS_READ, Perm.REVIEWS_WRITE,
    ]),

    ROLE_MANAGER: frozenset([
        Perm.CATALOG_READ,
        Perm.PRODUCTS_READ, Perm.PRODUCTS_WRITE,
        Perm.ORDERS_READ, Perm.ORDERS_WRITE,
        Perm.STATS_READ,
        Perm.SETTINGS_READ,
        Perm.FAQ_READ, Perm.FAQ_WRITE,
        Perm.IMPORT_WRITE,
        Perm.MEMBERS_READ,
        Perm.PROMOS_READ, Perm.PROMOS_WRITE,
        Perm.REVIEWS_READ, Perm.REVIEWS_WRITE,
    ]),

    ROLE_SUPPORT: frozenset([
        Perm.CATALOG_READ,
        Perm.ORDERS_READ, Perm.ORDERS_WRITE,
        Perm.STATS_READ,
        Perm.SETTINGS_READ,
        Perm.FAQ_READ,
        Perm.MEMBERS_READ,
        Perm.PROMOS_READ,
        Perm.REVIEWS_READ,
    ]),
}


def get_permissions(role: str) -> frozenset[str]:
    """Возвращает набор прав для роли. Пустой frozenset для неизвестных ролей."""
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: str, permission: str) -> bool:
    """Проверяет наличие конкретного права у роли."""
    perms = get_permissions(role)
    return "*" in perms or permission in perms
