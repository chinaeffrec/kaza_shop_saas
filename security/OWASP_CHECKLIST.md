# OWASP Top 10 — Kaza Shop Security Checklist

_Last reviewed: 2026-05-14_

## A01:2021 — Broken Access Control

| Check | Status | Notes |
|---|---|---|
| All endpoints protected by `require_platform_auth` or `require_bot_auth` | ✅ PASS | `app/api/deps.py` enforces JWT on all non-public routes |
| IDOR: `shop_id` from JWT, never from request body on write endpoints | ✅ PASS | `require_shop_id()` / `get_owner_shop_id()` injects from token |
| `assert_shop_access()` called when shop_id must match request param | ✅ PASS | Used in members, audit-logs, platform-scoped ops |
| Super-admin routes separated under `/platform/*` with `require_super_admin` | ✅ PASS | 403 for non-super_admin users |
| Impersonation token carries `impersonated_by` claim; full audit logged | ✅ PASS | `platform_control.py` logs WARNING + audit row |
| 2FA challenge token scope check (`scope == "totp_challenge"`) | ✅ PASS | `decode_totp_challenge_token` validates scope; missing `role` blocks access if misused |

**Manual pen-test (IDOR):**
```
# Test: owner of shop 1 trying to access shop 2 orders
curl -H "Authorization: Bearer <shop1_token>" \
     "https://api.example.com/api/v1/orders/?shop_id=2"
# Expected: 200 with shop 1 orders only (shop_id from JWT, not query param)
```

---

## A02:2021 — Cryptographic Failures

| Check | Status | Notes |
|---|---|---|
| Passwords hashed with bcrypt (rounds=12) | ✅ PASS | `platform_auth_service.hash_password()` |
| JWT signed with HS256; secret validated on startup | ✅ PASS | `_require_platform_secret()` raises if unset |
| Bot tokens encrypted with Fernet (AES-128-CBC + HMAC) | ✅ PASS | `app/services/bot_token_service.py` |
| Sensitive settings (CDEK secret, YooKassa key) stored encrypted | ✅ PASS | Fernet encryption in settings service |
| Refresh tokens: opaque UUID4 in Redis; no sensitive data in JWT | ✅ PASS | `prt:{jti}` → `user_id` in Redis |
| TLS enforced in production (HTTPSRedirectMiddleware) | ✅ PASS | `is_production=True` enables redirect |
| HSTS header added on HTTPS responses | ✅ PASS | `SecurityHeadersMiddleware` |
| TOTP secrets encrypted at rest | ✅ PASS | `encrypt_totp_secret()` / `decrypt_totp_secret()` in `platform_auth_service.py` — Fernet AES-128-CBC + HMAC, `enc:` prefix distinguishes ciphertext from legacy plaintext |

---

## A03:2021 — Injection

| Check | Status | Notes |
|---|---|---|
| All DB queries use SQLAlchemy ORM / parameterized queries | ✅ PASS | No raw string SQL in ORM calls |
| File paths sanitised via `sanitize_filename()` | ✅ PASS | `app/core/security.sanitize_filename()` |
| Upload filenames not used directly in shell commands | ✅ PASS | Files saved with UUID prefix |
| Pydantic validates all request bodies (type + length constraints) | ✅ PASS | All schemas use `Field(max_length=...)` |

---

## A04:2021 — Insecure Design

| Check | Status | Notes |
|---|---|---|
| Rate limiting on login: 5 attempts / 60s per IP | ✅ PASS | Redis-backed; fails closed if Redis down (503) |
| Order total recalculated server-side (not trusted from client) | ✅ PASS | `order_service` recomputes from cart items |
| Promo discount calculated server-side | ✅ PASS | `promo_service.apply_promo()` |
| Deferred 2FA setup: secret stored but not activated until verify | ✅ PASS | `profile/2fa/setup` + `verify` two-step flow |
| `X-Confirm-Destructive` header required for db-import / media-import | ✅ PASS | Checked in settings route |

---

## A05:2021 — Security Misconfiguration

| Check | Status | Notes |
|---|---|---|
| `docs_url`, `redoc_url`, `openapi_url` disabled in production | ✅ PASS | `None` when `is_production=True` |
| Strict CSP: `default-src 'none'; frame-ancestors 'none'` on API responses | ✅ PASS | `SecurityHeadersMiddleware` |
| Mini App CSP: `script-src 'self'` (eval forbidden) | ✅ PASS | Separate CSP block for `/api/v1/miniapp/*` |
| `X-Content-Type-Options: nosniff` | ✅ PASS | All responses |
| `X-Frame-Options: SAMEORIGIN` | ✅ PASS | All responses |
| Trusted hosts middleware: only allows configured domain + containers | ✅ PASS | `TrustedHostMiddleware` in `main.py` |
| Default credentials changed: `SUPER_ADMIN_PASSWORD` must be set | ✅ PASS | Startup validation; documented in RUNBOOK |

---

## A06:2021 — Vulnerable and Outdated Components

| Check | Status | Notes |
|---|---|---|
| `pip-audit` run in CI against `requirements.txt` | ✅ PASS | `scripts/security_audit.sh --ci` |
| `bandit` run in CI with MEDIUM+ severity threshold | ✅ PASS | Same script |
| Dependencies pinned to minor version ranges (e.g. `>=2.0,<3.0`) | ✅ PASS | `requirements.txt` uses range pins |
| Node dependencies audited with `npm audit` | ✅ PASS | `.github/workflows/security.yml` — `npm audit --audit-level=high` on every push to main |

---

## A07:2021 — Identification and Authentication Failures

| Check | Status | Notes |
|---|---|---|
| Access tokens: short TTL (1h), refresh tokens: 30d | ✅ PASS | Configurable via `ACCESS_TOKEN_TTL` |
| Refresh token rotation: old invalidated on use | ✅ PASS | Replay attack deletes both tokens |
| Token invalidated on password change via `mark_password_changed()` | ✅ PASS | Redis timestamp checked on every request |
| TOTP (2FA) available for all platform users | ✅ PASS | `POST /api/v1/profile/2fa/setup` |
| 2FA login: challenge token is short-lived (5 min), scoped | ✅ PASS | `scope: "totp_challenge"` in JWT |
| Password min length 10 chars, requires letter + digit | ✅ PASS | Pydantic validator in schema |
| Session logout: refresh token revoked in Redis | ✅ PASS | `POST /platform/auth/logout` |

---

## A08:2021 — Software and Data Integrity Failures

| Check | Status | Notes |
|---|---|---|
| File uploads: extension + magic bytes checked | ✅ PASS | `check_image_magic()` in profile upload |
| Product photo uploads: magic bytes validated | ✅ PASS | `settings_service_ext.py` `_upload_file()` now calls `check_image_magic()` for JPEG/PNG/WebP and `_check_svg_magic()` for SVG |
| Alembic migrations have `down_revision` chain integrity | ✅ PASS | Sequential 0001–0024 |
| No deserialization of untrusted data (pickle, yaml.load) | ✅ PASS | Only Pydantic / json.loads used |

---

## A09:2021 — Security Logging and Monitoring Failures

| Check | Status | Notes |
|---|---|---|
| Structured JSON logging with `trace_id` per request | ✅ PASS | `logging_setup.py` + `TraceIDMiddleware` |
| Audit log for all critical operations (create/delete/impersonate) | ✅ PASS | `AuditLog` model + service |
| Failed login attempts logged (rate-limit hit) | ✅ PASS | `platform_auth_service.check_login_rate_limit` |
| Impersonation events logged at WARNING level + audit row | ✅ PASS | `platform_control.py` |
| Circuit breaker state changes logged | ✅ PASS | `circuit_breaker.py` |
| Log retention and rotation configured | ✅ PASS | `RotatingFileHandler` 10MB × 5 files |

---

## A10:2021 — Server-Side Request Forgery (SSRF)

| Check | Status | Notes |
|---|---|---|
| `miniapp_url` validated: HTTPS only, no private IPs | ✅ PASS | `validate_url()` in `settings.py` PATCH |
| `yookassa_return_url` validated: HTTPS only | ✅ PASS | Same validator |
| CDEK API base URL hardcoded (not from user input) | ✅ PASS | `_PROD_BASE` / `_TEST_BASE` constants |
| YooKassa API base URL hardcoded | ✅ PASS | `_BASE` constant in `yookassa_client.py` |
| No server-side fetch of user-supplied URLs | ✅ PASS | All outbound HTTP uses hardcoded endpoints |
| DNS rebinding prevention: `check_dns=False` by default | ⚠️ WARN | Consider `check_dns=True` for `miniapp_url` if server fetches it |

---

## Critical Pen-Test Flows

### JWT Algorithm Confusion
```bash
# Attack: submit token with alg=none
# Defense: PyJWT with algorithms=["HS256"] rejects alg=none automatically
# Verify: token with {"alg":"none"} → 401 Invalid token
```

### IDOR via shop_id substitution
```bash
# Attack: include ?shop_id=2 while authenticated as shop 1 owner
# GET /api/v1/orders/?shop_id=2
# Defense: shop_id always taken from JWT (ctx.shop_id), query param ignored
# Test: grep for "shop_id" in query params → none should override ctx.shop_id
```

### Insecure Direct Object Reference on orders
```bash
# Attack: GET /api/v1/orders/9999 where order 9999 belongs to shop 2
# Defense: all order queries include WHERE shop_id=<jwt_shop_id>
# Verify: order service always filters by shop_id from auth context
```

### Refresh token replay
```bash
# 1. Capture refresh token: POST /platform/auth/refresh → new_jti
# 2. Replay old_jti: POST /platform/auth/refresh {"refresh_token": old_jti}
# Defense: old token deleted before issuing new one; replay returns 401
```

---

## Remediation Priority

| # | Finding | Severity | Status | Action |
|---|---|---|---|---|
| 1 | `totp_secret` stored as plaintext | MEDIUM | ✅ FIXED | `encrypt_totp_secret()` / `decrypt_totp_secret()` added; legacy plaintext handled transparently |
| 2 | Product photo upload magic bytes check | MEDIUM | ✅ FIXED | `_upload_file()` in `settings_service_ext.py` now validates magic bytes |
| 3 | `npm audit` not in CI | LOW | ✅ FIXED | `.github/workflows/security.yml` runs `npm audit --audit-level=high` + Bandit + pip-audit + TruffleHog |
| 4 | `check_dns=True` for miniapp_url | LOW | ⚠️ OPEN | Enable if the server ever fetches the miniapp_url |
