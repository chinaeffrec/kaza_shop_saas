"""
Kaza Shop — Locust load test scenarios.

Simulates real Telegram-bot traffic patterns:
  BotBrowseUser   — reads catalog, checks product details (80% of traffic)
  BotCartUser     — adds items to cart, views cart (15% of traffic)
  BotOrderUser    — full checkout flow: browse → cart → order (5% of traffic)
  SellerPanelUser — seller panel API calls (separate scenario)

Usage:
  pip install locust
  locust -f tests/load/locustfile.py --host=http://localhost:8000

  # Headless with 100 users, 10/s spawn rate, run 2 minutes:
  locust -f tests/load/locustfile.py --host=http://localhost:8000 \
         --headless -u 100 -r 10 --run-time 2m --html results.html

Environment variables:
  BOT_TOKEN_TEST  — valid BOT_API_TOKEN for X-Bot-Token header
  SHOP_ID_TEST    — shop ID to test against (default: 1)
  SELLER_EMAIL    — seller panel login email
  SELLER_PASSWORD — seller panel login password
"""
from __future__ import annotations

import os
import random
import string
from typing import Optional

from locust import HttpUser, TaskSet, between, events, tag, task

# ── Config from env ───────────────────────────────────────────────────────────
BOT_TOKEN    = os.getenv("BOT_TOKEN_TEST", "test-bot-token")
SHOP_ID      = int(os.getenv("SHOP_ID_TEST", "1"))
SELLER_EMAIL = os.getenv("SELLER_EMAIL", "admin@example.com")
SELLER_PASS  = os.getenv("SELLER_PASSWORD", "changeme")

_BOT_HEADERS = {
    "X-Bot-Token":   BOT_TOKEN,
    "X-Bot-Shop-Id": str(SHOP_ID),
}

_PRODUCT_IDS: list[int] = []   # populated on first successful catalog fetch
_CATEGORY_IDS: list[int] = []


def _rand_tg_id() -> int:
    """Generate a random Telegram user ID in the valid range."""
    return random.randint(100_000, 999_999_999)


# ── Bot user base class ───────────────────────────────────────────────────────

class BotBase(HttpUser):
    abstract = True
    wait_time = between(1, 3)  # seconds between tasks

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tg_id = _rand_tg_id()
        self._bot_headers = _BOT_HEADERS | {"X-Bot-User-Id": str(self.tg_id)}

    def on_start(self):
        """Register the bot user at session start."""
        self.client.post(
            "/api/v1/users/register",
            json={
                "id": self.tg_id,
                "username": f"loadtest_{self.tg_id}",
                "first_name": "Load",
                "last_name": "Test",
            },
            headers=self._bot_headers,
            name="/api/v1/users/register",
        )
        # Warm up product list
        self._fetch_product_list()

    def _fetch_product_list(self):
        with self.client.get(
            f"/api/v1/products/?page=1&per_page=20&shop_id={SHOP_ID}",
            headers=self._bot_headers,
            name="/api/v1/products/ [list]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items") or data if isinstance(data, list) else []
                global _PRODUCT_IDS
                if items:
                    _PRODUCT_IDS = [p["id"] for p in items[:50]]
            else:
                resp.failure(f"Product list failed: {resp.status_code}")


# ── Scenario 1: Catalog browser (80% of bot traffic) ─────────────────────────

class BotBrowseUser(BotBase):
    weight = 80

    @task(3)
    @tag("catalog")
    def browse_products(self):
        self.client.get(
            f"/api/v1/products/?page=1&per_page=20",
            headers=self._bot_headers,
            name="/api/v1/products/ [browse]",
        )

    @task(2)
    @tag("catalog")
    def view_product_detail(self):
        if not _PRODUCT_IDS:
            return
        pid = random.choice(_PRODUCT_IDS)
        self.client.get(
            f"/api/v1/products/{pid}",
            headers=self._bot_headers,
            name="/api/v1/products/{id}",
        )

    @task(1)
    @tag("catalog")
    def get_public_settings(self):
        self.client.get(
            "/api/v1/settings/public",
            headers=self._bot_headers,
            name="/api/v1/settings/public",
        )

    @task(1)
    @tag("catalog")
    def get_categories(self):
        self.client.get(
            "/api/v1/catalog/categories",
            headers=self._bot_headers,
            name="/api/v1/catalog/categories",
        )


# ── Scenario 2: Cart user (15% of bot traffic) ───────────────────────────────

class BotCartUser(BotBase):
    weight = 15

    def on_start(self):
        super().on_start()
        self._clear_cart()

    def _clear_cart(self):
        self.client.delete(
            "/api/v1/cart/",
            headers=self._bot_headers,
            name="/api/v1/cart/ [clear]",
        )

    @task(2)
    @tag("cart")
    def add_to_cart(self):
        if not _PRODUCT_IDS:
            return
        pid = random.choice(_PRODUCT_IDS)
        self.client.post(
            "/api/v1/cart/",
            json={"product_id": pid, "quantity": random.randint(1, 3)},
            headers=self._bot_headers,
            name="/api/v1/cart/ [add]",
        )

    @task(1)
    @tag("cart")
    def view_cart(self):
        self.client.get(
            "/api/v1/cart/",
            headers=self._bot_headers,
            name="/api/v1/cart/ [get]",
        )

    @task(1)
    @tag("cart")
    def remove_from_cart(self):
        if not _PRODUCT_IDS:
            return
        pid = random.choice(_PRODUCT_IDS)
        self.client.delete(
            f"/api/v1/cart/{pid}",
            headers=self._bot_headers,
            name="/api/v1/cart/{id} [remove]",
        )


# ── Scenario 3: Full checkout user (5% of bot traffic) ───────────────────────

class BotOrderUser(BotBase):
    weight = 5

    def on_start(self):
        super().on_start()
        # Add 1-2 items to cart for order creation
        self._prepare_cart()

    def _prepare_cart(self):
        if not _PRODUCT_IDS:
            return
        self.client.delete("/api/v1/cart/", headers=self._bot_headers, name="/api/v1/cart/ [clear-pre-order]")
        for _ in range(random.randint(1, 2)):
            pid = random.choice(_PRODUCT_IDS)
            self.client.post(
                "/api/v1/cart/",
                json={"product_id": pid, "quantity": 1},
                headers=self._bot_headers,
                name="/api/v1/cart/ [add-pre-order]",
            )

    @task(1)
    @tag("order")
    def create_order(self):
        self._prepare_cart()
        # Generate random delivery address
        city = random.choice(["Москва", "Санкт-Петербург", "Казань"])
        with self.client.post(
            "/api/v1/orders/",
            json={
                "comment": "Load test order",
                "delivery_address": f"г. {city}, ул. Тестовая, д. {random.randint(1, 100)}",
            },
            headers=self._bot_headers,
            name="/api/v1/orders/ [create]",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 201):
                resp.success()
            elif resp.status_code == 400:
                # Empty cart — expected if cart wasn't populated
                resp.success()
            else:
                resp.failure(f"Order creation failed: {resp.status_code}")


# ── Scenario 4: Seller Panel user ────────────────────────────────────────────

class SellerPanelUser(HttpUser):
    """
    Simulates a shop owner actively using the seller panel.
    Low wait time — seller is actively working.
    """
    weight = 10
    wait_time = between(2, 6)
    _token: Optional[str] = None

    def on_start(self):
        self._login()

    def _login(self):
        with self.client.post(
            "/platform/auth/login",
            json={"email": SELLER_EMAIL, "password": SELLER_PASS},
            name="/platform/auth/login",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if data.get("requires_totp"):
                    # 2FA is enabled — can't proceed without manual TOTP
                    resp.failure("2FA enabled — set SELLER_EMAIL/SELLER_PASSWORD to an account without 2FA")
                    return
                self._token = data.get("access_token")
                resp.success()
            else:
                resp.failure(f"Login failed: {resp.status_code} {resp.text[:100]}")

    def _auth_headers(self) -> dict:
        if not self._token:
            return {}
        return {"Authorization": f"Bearer {self._token}"}

    @task(3)
    @tag("seller")
    def list_orders(self):
        self.client.get(
            "/api/v1/orders/?status=new&page=1&per_page=20",
            headers=self._auth_headers(),
            name="/api/v1/orders/ [new]",
        )

    @task(2)
    @tag("seller")
    def list_products(self):
        self.client.get(
            "/api/v1/products/?page=1&per_page=20",
            headers=self._auth_headers(),
            name="/api/v1/products/ [seller]",
        )

    @task(1)
    @tag("seller")
    def dashboard_stats(self):
        self.client.get(
            "/api/v1/stats/dashboard",
            headers=self._auth_headers(),
            name="/api/v1/stats/dashboard",
        )

    @task(1)
    @tag("seller")
    def get_settings(self):
        self.client.get(
            "/api/v1/settings/",
            headers=self._auth_headers(),
            name="/api/v1/settings/",
        )

    @task(1)
    @tag("seller")
    def health_check(self):
        self.client.get("/health", name="/health")


# ── Event hooks ───────────────────────────────────────────────────────────────

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print(f"\n[Kaza Load Test] Starting against {environment.host}")
    print(f"  Shop ID: {SHOP_ID}")
    print(f"  Seller: {SELLER_EMAIL}\n")
