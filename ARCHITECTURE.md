# Kaza Shop — Architecture Overview

## System Overview

Kaza Shop is a **multi-tenant SaaS platform** that lets merchants run Telegram bot storefronts. Each merchant gets their own Telegram bot, but all bots share a single FastAPI backend (multi-tenant via `shop_id`).

---

## Component Diagram

```
                         ┌─────────────────────────────────────────────┐
                         │             Internet / Telegram              │
                         └───────┬──────────────────┬───────────────────┘
                                 │                  │
                    ┌────────────▼────────┐  ┌──────▼────────────────┐
                    │  Telegram Bot API   │  │   Telegram Mini App   │
                    │  (aiogram v3 webhk) │  │   (Vite/React SPA)    │
                    └────────────┬────────┘  └──────┬────────────────┘
                                 │                  │ HTTPS
                    ┌────────────▼──────────────────▼────────────────────┐
                    │                    Nginx                            │
                    │  TLS termination · rate limit · static media        │
                    │  Upstream: app1:8000, app2:8000 (least_conn)        │
                    └──────────────┬─────────────────────────────────────┘
                                   │
                    ┌──────────────▼─────────────────────────────────────┐
                    │              FastAPI Application                    │
                    │                                                     │
                    │  /platform/auth/*   — platform user auth (JWT)      │
                    │  /platform/*        — super-admin control           │
                    │  /api/v1/products   — catalog CRUD                  │
                    │  /api/v1/orders     — order lifecycle               │
                    │  /api/v1/cart       — shopping cart                 │
                    │  /api/v1/stats      — analytics                     │
                    │  /api/v1/settings   — shop configuration            │
                    │  /api/v1/cdek       — CDEK shipping                 │
                    │  /api/v1/yookassa   — online payments               │
                    │  /api/v1/miniapp    — Mini App auth & catalog       │
                    │  /api/v1/reviews    — product reviews               │
                    │  /api/v1/billing    — plan management               │
                    │  /api/v1/profile    — user profile + 2FA            │
                    │  /metrics           — Prometheus (optional)         │
                    └────────┬──────────┬──────────────┬──────────────────┘
                             │          │              │
              ┌──────────────▼──┐  ┌────▼─────┐  ┌───▼──────────────────┐
              │   PostgreSQL     │  │  Redis   │  │  External APIs       │
              │   (primary)      │  │  master  │  │  ┌──────────────┐    │
              │   + replica      │  │  + repl  │  │  │ CDEK API v2  │    │
              │   + PgBouncer    │  │  + 3×    │  │  │ YooKassa v3  │    │
              │                  │  │ Sentinel │  │  │ Telegram API │    │
              └──────────────────┘  └──────────┘  │  └──────────────┘    │
                                                   └──────────────────────┘

  Observability:
  ┌────────────────────────────────────────────────────────────────────┐
  │  Prometheus (/metrics)  →  Grafana dashboards                      │
  │  JSON logs + trace_id   →  stdout → log aggregator (Loki / ELK)   │
  └────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
kaza_shop_saas/
├── app/                        # FastAPI application
│   ├── api/
│   │   ├── deps.py             # Auth dependencies (JWT, RBAC, bot auth)
│   │   ├── routes/             # One file per resource
│   │   └── schemas/            # Pydantic I/O schemas
│   ├── core/
│   │   ├── circuit_breaker.py  # CLOSED/OPEN/HALF_OPEN for CDEK & YooKassa
│   │   ├── config.py           # Settings (pydantic-settings, env vars)
│   │   ├── maintenance.py      # Platform-wide maintenance mode (Redis)
│   │   ├── middleware.py       # TraceID, HTTPS redirect, security headers
│   │   ├── rbac.py             # Role-permission matrix
│   │   ├── redis_client.py     # Redis + Sentinel client
│   │   └── security.py         # SSRF validator, magic bytes checker
│   ├── db/
│   │   ├── alembic_runner.py   # Auto-runs migrations on startup
│   │   ├── engine.py           # AsyncEngine (PgBouncer-aware)
│   │   └── session.py          # AsyncSession + tenacity retry
│   ├── integrations/
│   │   ├── cdek_client.py      # CDEK API v2 (circuit breaker wrapped)
│   │   └── yookassa_client.py  # YooKassa API v3 (circuit breaker wrapped)
│   ├── models/                 # SQLAlchemy ORM models
│   ├── services/               # Business logic layer
│   └── main.py                 # FastAPI app, middleware stack, lifespan
├── alembic/                    # Database migrations (0001–0024)
├── seller-panel/               # React (Vite) seller admin SPA
│   └── src/
│       ├── hooks/              # useTheme, useKeyboardShortcuts
│       ├── components/         # Toast, NotificationCenter, OnboardingWizard
│       └── pages/              # One component per page
├── deploy/                     # Infrastructure configuration
│   ├── nginx/                  # Nginx HA config
│   ├── pgbouncer/              # PgBouncer config
│   ├── postgres/               # Replica init script, pg_hba.conf
│   ├── redis/                  # Sentinel config
│   ├── prometheus/             # Scrape config
│   └── grafana/                # Provisioning (datasource + dashboard)
├── tests/
│   └── load/                   # Locust + k6 load test scripts
├── scripts/                    # Operational scripts
├── security/                   # Security audit artifacts
├── docker-compose.yml          # Single-node dev/prod
├── docker-compose.ha.yml       # HA stack (2 app + PgBouncer + Sentinel + MinIO)
├── ARCHITECTURE.md             # This document
└── RUNBOOK.md                  # Operational runbook
```

---

## Data Flow: Telegram Bot → Order Creation

```
User in Telegram
      │
      │ /start or /catalog
      ▼
aiogram Bot Process
  (separate Docker container)
      │
      │ POST /api/v1/catalog/categories
      │ POST /api/v1/products/
      │ POST /api/v1/cart/
      │  Headers: X-Bot-Token, X-Bot-Shop-Id, X-Bot-User-Id
      ▼
FastAPI (require_bot_auth)
  ├── Validates X-Bot-Token == BOT_API_TOKEN
  ├── Checks Shop.status == "active" in DB
  └── Returns BotAuthContext{shop_id, user_id}
      │
      │ POST /api/v1/orders/
      ▼
order_service.create_order()
  ├── Reads CartItem rows for (shop_id, user_id)
  ├── Validates product availability + stock
  ├── Applies promo code discount (if any)
  ├── Writes Order + OrderItem rows
  ├── Clears cart
  └── Sends Telegram notification to admin_contact
      │
      ▼
  Order saved in PostgreSQL
  Notification sent to shop owner via Telegram
```

---

## Data Flow: YooKassa Payment

```
Seller enables YooKassa in Settings
      │
Customer clicks "Pay online"
      │
POST /api/v1/yookassa/payments/{order_id}
  ├── Reads shop YooKassa credentials (Fernet-decrypted)
  ├── Calls yookassa_client.create_payment()  [circuit breaker]
  └── Returns { confirmation_url }
      │
Customer redirected to YooKassa checkout
      │
YooKassa sends webhook:
POST /api/v1/yookassa/webhook
  ├── Verifies webhook signature (IP allowlist + signature header)
  ├── Finds Order by payment_id [indexed]
  ├── Updates Order.payment_status
  └── If succeeded → notifies bot → order status "paid"
```

---

## Multi-Tenancy Model

Every row with business data carries a `shop_id` foreign key.
Auth layer injects `shop_id` from the JWT token — it is **never trusted from request body or query params** on write operations.

```
PlatformUser (seller account)
    │ 1:N
    ▼
Shop (shop_id, status, plan, bot_token_encrypted)
    │ 1:N
    ├── ShopSettings
    ├── Product
    ├── Order → OrderItem
    ├── CartItem
    ├── PromoCode
    ├── Review
    ├── FaqItem
    └── ShopMember  (RBAC: owner / manager / support)
```

---

## Authentication Architecture

```
                    ┌─────────────────────────────┐
                    │   POST /platform/auth/login  │
                    │   email + password           │
                    └────────────┬────────────────┘
                                 │ bcrypt verify
                                 │
                         totp_enabled? ──YES──► TotpChallengeResponse
                                 │              (5-min JWT, scope=totp_challenge)
                                 NO               │
                                 │         POST /platform/auth/2fa/verify
                                 │         challenge_token + TOTP code
                                 │               │ pyotp.TOTP.verify(±30s)
                                 ▼               ▼
                    ┌────────────────────────────────────────┐
                    │         TokenResponse                   │
                    │  access_token  (JWT HS256, 1h TTL)     │
                    │  refresh_token (opaque UUID4, Redis)    │
                    └────────────┬───────────────────────────┘
                                 │
                    ┌────────────▼───────────────────────────┐
                    │         require_platform_auth           │
                    │  1. Decode JWT → payload                │
                    │  2. Check is_token_invalidated (Redis)  │
                    │  3. Return PlatformAuthContext          │
                    │     {user_id, role, shop_id, perms}     │
                    └────────────────────────────────────────┘
```

---

## High Availability Architecture

```
                    ┌─────────────────────────────────────────────────┐
                    │                  Nginx (upstream)                │
                    │         least_conn, max_fails=3 fail_timeout=30s │
                    └────────────────┬───────────────┬─────────────────┘
                                     │               │
                              ┌──────▼──────┐ ┌──────▼──────┐
                              │    app1     │ │    app2     │
                              │  :8000      │ │  :8000      │
                              └──────┬──────┘ └──────┬──────┘
                                     │               │
                              ┌──────▼───────────────▼──────┐
                              │         PgBouncer            │
                              │   transaction pooling        │
                              │   pool_size=20               │
                              └──────────────┬──────────────┘
                                             │
                    ┌────────────────────────▼────────────────────────┐
                    │  PostgreSQL primary  ──── pg-replica (streaming) │
                    │  WAL shipping to MinIO (optional PITR)           │
                    └─────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────────────────┐
                    │  redis-master ──── redis-replica                 │
                    │       │                                          │
                    │  sentinel1, sentinel2, sentinel3 (quorum=2)      │
                    └─────────────────────────────────────────────────┘
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Single FastAPI process, multi-tenant via `shop_id` | Simpler ops than per-tenant containers; Redis/PG handle isolation |
| aiogram bot in separate container | Bot process crash doesn't affect API; clean separation |
| PgBouncer in transaction mode | Reduces PG connection count from N×pool_size to pool_size |
| Circuit breaker (in-process) for CDEK/YooKassa | Fast fail-open; avoids cascading failures from external API outages |
| Redis Sentinel (not Cluster) | Sentinel sufficient for <100k req/day; simpler than Cluster |
| Fernet for bot tokens + secrets | Reversible encryption needed (must decrypt for API calls) |
| Refresh token rotation | Any token theft is detected on next valid use; self-healing |
| Postgres partial indexes on nullable columns | `WHERE payment_id IS NOT NULL` avoids bloating index with NULLs |
