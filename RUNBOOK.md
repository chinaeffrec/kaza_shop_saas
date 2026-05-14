# Kaza Shop — Operations Runbook

_Last updated: 2026-05-14_

## Table of Contents

1. [First-Time Deployment (from scratch)](#1-first-time-deployment-from-scratch)
2. [Updating a Running Instance](#2-updating-a-running-instance)
3. [HA Stack Deployment](#3-ha-stack-deployment)
4. [Database Migrations](#4-database-migrations)
5. [Rollback Procedures](#5-rollback-procedures)
6. [Managing the Telegram Bot](#6-managing-the-telegram-bot)
7. [Secrets & Credentials Rotation](#7-secrets--credentials-rotation)
8. [Backup and Restore](#8-backup-and-restore)
9. [Health Checks & Monitoring](#9-health-checks--monitoring)
10. [Incident Response](#10-incident-response)
11. [Scaling](#11-scaling)
12. [Maintenance Mode](#12-maintenance-mode)
13. [Common Issues & Fixes](#13-common-issues--fixes)

---

## 1. First-Time Deployment (from scratch)

### Prerequisites

```
OS:       Ubuntu 22.04 LTS (recommended) or Debian 12
CPU:      2 vCPU minimum (4 recommended for production)
RAM:      2 GB minimum (4 GB for HA stack)
Disk:     20 GB SSD minimum
Software: Docker ≥ 24.0, Docker Compose ≥ 2.20, Git
Domain:   DNS A-record pointing to server IP
Ports:    80, 443 open inbound; 22 for SSH
```

### Step 1 — Clone the repository

```bash
git clone https://github.com/your-org/kaza_shop_saas.git /opt/kaza
cd /opt/kaza
```

### Step 2 — Create the environment file

```bash
cp .env.example .env
nano .env
```

Required variables (all others have defaults):

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL async DSN | `postgresql+asyncpg://kaza:pass@db:5432/kaza` |
| `REDIS_URL` | Redis DSN | `redis://redis:6379/0` |
| `SECRET_KEY` | JWT signing key, ≥32 random chars | `openssl rand -hex 32` |
| `FERNET_KEY` | Fernet key for token encryption | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `BOT_API_TOKEN` | Telegram bot token from @BotFather | `7123456789:AAF...` |
| `SUPER_ADMIN_EMAIL` | Initial super-admin email | `admin@example.com` |
| `SUPER_ADMIN_PASSWORD` | Initial super-admin password (≥10 chars) | change-me-immediately |
| `ALLOWED_HOSTS` | Comma-separated domains | `api.example.com,localhost` |
| `DOMAIN` | Public domain for HTTPS redirect | `api.example.com` |

Optional integrations:

```bash
YOOKASSA_SHOP_ID=
YOOKASSA_SECRET_KEY=
CDEK_CLIENT_ID=
CDEK_CLIENT_SECRET=
```

### Step 3 — Build and start

```bash
# Build images and start all services
docker compose up -d --build

# Follow startup logs (Ctrl+C to detach, services keep running)
docker compose logs -f app
```

### Step 4 — Verify startup

```bash
# Health check
curl -s http://localhost:8000/health | python3 -m json.tool

# Expected:
# { "status": "ok", "db": "ok", "redis": "ok" }
```

### Step 5 — Create the first super-admin

The super-admin is created automatically on startup if `SUPER_ADMIN_EMAIL` and
`SUPER_ADMIN_PASSWORD` are set in `.env`. Check the app logs for confirmation:

```bash
docker compose logs app | grep -i "super.admin"
```

If not created automatically:

```bash
docker compose exec app python3 -m app.scripts.create_superadmin \
    --email admin@example.com \
    --password 'YourSecurePassword!'
```

### Step 6 — Set up Nginx (production)

```bash
# Copy Nginx config
cp deploy/nginx/nginx.ha.conf /etc/nginx/sites-available/kaza
ln -s /etc/nginx/sites-available/kaza /etc/nginx/sites-enabled/kaza

# Obtain TLS certificate (certbot)
apt install -y certbot python3-certbot-nginx
certbot --nginx -d api.example.com -d www.example.com

# Test and reload
nginx -t && systemctl reload nginx
```

### Step 7 — Set Telegram webhook

```bash
# Replace BOT_TOKEN and DOMAIN with actual values
curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://api.example.com/webhook/${BOT_TOKEN}", "drop_pending_updates": true}'

# Verify
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool
```

---

## 2. Updating a Running Instance

### Standard update (zero-downtime via `deploy.sh`)

```bash
# From your local machine or CI server
bash deploy.sh --ip <server-ip> --key ~/.ssh/id_rsa
```

The script:
1. Creates a code archive (excludes `.env`, media, DB volumes)
2. Uploads to server
3. Creates a DB snapshot on the server and sends it to Telegram
4. Stops `app` and `bot` containers
5. Replaces code, rebuilds images
6. Starts containers, waits for `/health` to return `200`
7. On failure: automatically rolls back to previous image

### Manual update

```bash
cd /opt/kaza

# Pull latest code
git pull origin main

# Rebuild and restart (app only, no downtime on bot)
docker compose up -d --build --no-deps app

# Check new containers are healthy
docker compose ps
curl -s http://localhost:8000/health
```

---

## 3. HA Stack Deployment

The HA stack uses `docker-compose.ha.yml` with:
- 2 app instances (`app1`, `app2`) behind Nginx `least_conn`
- PgBouncer in transaction pooling mode
- PostgreSQL primary + streaming replica
- Redis master + replica + 3 Sentinels

```bash
# Start HA stack (first time)
docker compose -f docker-compose.ha.yml up -d --build

# Scale app instances (add a third if needed)
docker compose -f docker-compose.ha.yml up -d --scale app=3 --no-deps app

# Check all services are healthy
docker compose -f docker-compose.ha.yml ps
```

### Verify replication

```bash
# PostgreSQL streaming replication lag
docker compose -f docker-compose.ha.yml exec db \
    psql -U kaza -d kaza -c "SELECT * FROM pg_stat_replication;"

# Redis replication info
docker compose -f docker-compose.ha.yml exec redis-master \
    redis-cli info replication | grep -E "role|connected_slaves|master_replid"
```

### Sentinel status

```bash
docker compose -f docker-compose.ha.yml exec sentinel1 \
    redis-cli -p 26379 sentinel masters
```

---

## 4. Database Migrations

Migrations run automatically on startup via `app/db/alembic_runner.py`.
For manual control:

### Check current revision

```bash
docker compose exec app alembic current
```

### Apply all pending migrations

```bash
docker compose exec app alembic upgrade head
```

### Apply one migration at a time

```bash
docker compose exec app alembic upgrade +1
```

### Show migration history

```bash
docker compose exec app alembic history --verbose
```

### Generate a new migration (after changing SQLAlchemy models)

```bash
docker compose exec app alembic revision \
    --autogenerate \
    -m "describe_what_changed"

# Review the generated file in alembic/versions/
# Then apply:
docker compose exec app alembic upgrade head
```

> **Important**: Always review autogenerated migrations before applying.
> Check for unintended `DROP COLUMN` or `DROP TABLE` operations.

---

## 5. Rollback Procedures

### Roll back the last migration

```bash
# Downgrade one step
docker compose exec app alembic downgrade -1

# Downgrade to a specific revision
docker compose exec app alembic downgrade 0022

# Downgrade all the way to empty DB (DANGEROUS — destroys all data)
docker compose exec app alembic downgrade base
```

### Roll back to a previous application version

```bash
# On the server — check available image tags
docker images | grep kaza_shop_saas

# Restart app with a specific image tag
docker compose stop app
docker tag kaza_shop_saas-app:previous kaza_shop_saas-app:rollback
# Edit docker-compose.yml image: field, then:
docker compose up -d --no-deps app
```

### Roll back via git (emergency)

```bash
cd /opt/kaza

# Find last working commit
git log --oneline -10

# Hard reset to that commit
git checkout <commit-sha>

# Rebuild and restart
docker compose up -d --build --no-deps app
```

### Database point-in-time recovery (HA stack with MinIO WAL archiving)

```bash
# 1. Stop the application
docker compose -f docker-compose.ha.yml stop app1 app2 bot

# 2. Create recovery target timestamp (UTC)
TARGET="2026-05-14 10:30:00"

# 3. Edit postgres/recovery.conf (or postgresql.conf in PG 12+)
docker compose -f docker-compose.ha.yml exec db bash -c "
cat > /var/lib/postgresql/data/recovery.signal << EOF
EOF
cat >> /var/lib/postgresql/data/postgresql.conf << EOF
recovery_target_time = '${TARGET}'
recovery_target_action = 'promote'
EOF"

# 4. Restart PostgreSQL
docker compose -f docker-compose.ha.yml restart db

# 5. Verify recovery completed
docker compose -f docker-compose.ha.yml exec db \
    psql -U kaza -c "SELECT pg_is_in_recovery();"
# Expected: f (false = primary, recovery done)

# 6. Re-run migrations to re-apply any that post-date the recovery point
docker compose -f docker-compose.ha.yml exec app1 alembic upgrade head

# 7. Restart the app
docker compose -f docker-compose.ha.yml start app1 app2 bot
```

---

## 6. Managing the Telegram Bot

### Start / Stop / Restart

```bash
# Standard stack
docker compose restart bot
docker compose stop bot
docker compose start bot

# HA stack
docker compose -f docker-compose.ha.yml restart bot
```

### View bot logs

```bash
docker compose logs -f --tail=100 bot
```

### Reconfigure webhook after domain change

```bash
# Delete old webhook
curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook"

# Set new webhook
curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
     -H "Content-Type: application/json" \
     -d "{\"url\": \"https://NEW_DOMAIN/webhook/${BOT_TOKEN}\"}"
```

### Register a new bot for a merchant (via API)

```bash
curl -X POST https://api.example.com/platform/shops/ \
     -H "Authorization: Bearer <super_admin_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Shop Name",
       "owner_id": 42,
       "bot_token": "7123456789:AAF..."
     }'
```

### Bot not responding — diagnostics

```bash
# 1. Check container status
docker compose ps bot

# 2. Check recent errors
docker compose logs --tail=50 bot | grep -i "error\|exception\|traceback"

# 3. Test bot token validity
BOT_TOKEN=$(docker compose exec app env | grep BOT_API_TOKEN | cut -d= -f2)
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getMe"

# 4. Check webhook status
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
```

---

## 7. Secrets & Credentials Rotation

### Rotate JWT SECRET_KEY

> Rotating SECRET_KEY invalidates **all active access tokens** — users will be
> force-logged out. Schedule during low-traffic hours.

```bash
# 1. Generate new key
NEW_KEY=$(openssl rand -hex 32)

# 2. Update .env
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=${NEW_KEY}/" /opt/kaza/.env

# 3. Restart app (tokens are re-validated on next request)
docker compose up -d --no-deps app
```

### Rotate FERNET_KEY (bot token encryption)

> Rotating FERNET_KEY requires re-encrypting all stored bot tokens.
> **Do not simply replace the key** — decrypt first with the old key, then
> re-encrypt with the new key.

```bash
# 1. On the server, open a Python shell inside the app container
docker compose exec app python3

# 2. In the Python shell:
from app.core.config import settings
from cryptography.fernet import Fernet, MultiFernet

OLD_KEY = settings.FERNET_KEY  # current key
NEW_KEY = Fernet.generate_key()

# MultiFernet can decrypt with either key, so we can migrate safely
f = MultiFernet([Fernet(NEW_KEY), Fernet(OLD_KEY.encode())])

# Re-encrypt all shop bot tokens
import asyncio
from sqlalchemy import select, update
from app.db.session import get_async_session
from app.models.shop import Shop

async def rotate():
    async with get_async_session() as session:
        result = await session.execute(select(Shop).where(Shop.bot_token_encrypted != None))
        shops = result.scalars().all()
        for shop in shops:
            plaintext = Fernet(OLD_KEY.encode()).decrypt(shop.bot_token_encrypted.encode())
            shop.bot_token_encrypted = Fernet(NEW_KEY).encrypt(plaintext).decode()
        await session.commit()
        print(f"Rotated {len(shops)} shop tokens")

asyncio.run(rotate())
print("New FERNET_KEY:", NEW_KEY.decode())

# 3. Update .env with the new key and restart
```

### Rotate database password

```bash
# 1. Change password in PostgreSQL
docker compose exec db psql -U postgres -c \
    "ALTER USER kaza PASSWORD 'new-secure-password';"

# 2. Update DATABASE_URL in .env
sed -i "s|postgresql+asyncpg://kaza:[^@]*@|postgresql+asyncpg://kaza:new-secure-password@|" /opt/kaza/.env

# 3. Update PgBouncer userlist (HA stack)
# Hash the new password:
docker compose exec db psql -U postgres -c \
    "SELECT 'md5' || md5('new-secure-passwordkaza');"
# Update deploy/pgbouncer/userlist.txt with the hash

# 4. Restart app and PgBouncer
docker compose restart app
docker compose -f docker-compose.ha.yml restart pgbouncer
```

---

## 8. Backup and Restore

### Create a database backup

```bash
# Automatic (via backup.sh)
bash /opt/kaza/backup.sh

# Manual PostgreSQL dump
docker compose exec db pg_dump \
    -U kaza \
    --format=custom \
    --compress=9 \
    kaza > /opt/backups/kaza_$(date +%Y%m%d_%H%M%S).dump

# Verify backup integrity
pg_restore --list /opt/backups/kaza_*.dump | head -20
```

### Restore from backup

```bash
# 1. Stop the app (prevents writes during restore)
docker compose stop app bot

# 2. Drop and recreate the database
docker compose exec db psql -U postgres -c "DROP DATABASE kaza;"
docker compose exec db psql -U postgres -c "CREATE DATABASE kaza OWNER kaza;"

# 3. Restore
docker compose exec -T db pg_restore \
    -U kaza \
    -d kaza \
    --no-owner \
    --role=kaza < /opt/backups/kaza_YYYYMMDD_HHMMSS.dump

# 4. Run migrations to ensure schema is current
docker compose exec app alembic upgrade head

# 5. Start the app
docker compose start app bot
```

### Backup media files

```bash
# Backup uploads directory
tar -czf /opt/backups/media_$(date +%Y%m%d).tar.gz \
    /opt/kaza/uploads/

# Restore media
tar -xzf /opt/backups/media_YYYYMMDD.tar.gz -C /
```

---

## 9. Health Checks & Monitoring

### Application health endpoint

```bash
# Basic health (DB + Redis connectivity)
curl -s http://localhost:8000/health | python3 -m json.tool

# Expected response:
# {
#   "status": "ok",
#   "db": "ok",
#   "redis": "ok",
#   "version": "1.0.0"
# }
```

### Prometheus metrics

```bash
# Available when PROMETHEUS_ENABLED=true
curl -s http://localhost:8000/metrics | grep -E "^kaza_|^http_"

# Key metrics to watch:
#   http_request_duration_seconds   — latency histogram
#   http_requests_total             — request counts by status
#   kaza_orders_created_total       — business metric
```

### Grafana dashboards

Access at `http://localhost:3000` (default: `admin` / `admin` — **change on first login**).

Pre-provisioned dashboard: **Kaza Shop Overview**
- Panels: RPS, latency p50/p95/p99, 5xx error rate, DB connection pool, Redis ops/sec

### Checking container resource usage

```bash
docker stats --no-stream
```

### Log access

```bash
# Application logs (JSON structured)
docker compose logs --tail=200 app | python3 -m json.tool 2>/dev/null | grep -E '"level"|"message"'

# Filter by trace_id (from a request's X-Trace-Id response header)
docker compose logs app | grep '"trace_id":"abc123"'

# Filter errors only
docker compose logs app | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        r = json.loads(line)
        if r.get('level') in ('ERROR', 'CRITICAL'):
            print(line.rstrip())
    except: pass
"
```

---

## 10. Incident Response

### Service is down (500 errors)

```bash
# 1. Check container status
docker compose ps

# 2. Check for OOM kills
docker inspect kaza_shop_app | grep -A5 '"OOMKilled"'

# 3. Check recent errors
docker compose logs --tail=100 app | grep -i "error\|traceback\|exception"

# 4. Check DB connectivity
docker compose exec app python3 -c "
import asyncio
from app.db.session import get_async_session
from sqlalchemy import text

async def check():
    async with get_async_session() as s:
        r = await s.execute(text('SELECT 1'))
        print('DB OK:', r.scalar())

asyncio.run(check())
"

# 5. Check Redis
docker compose exec redis redis-cli ping

# 6. Restart app (last resort — causes brief downtime)
docker compose restart app
```

### Database is slow

```bash
# Find long-running queries
docker compose exec db psql -U kaza -d kaza -c "
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 seconds'
  AND state != 'idle'
ORDER BY duration DESC;
"

# Kill a specific query (replace <pid>)
docker compose exec db psql -U postgres -c "SELECT pg_cancel_backend(<pid>);"

# Check for table bloat / missing VACUUM
docker compose exec db psql -U kaza -d kaza -c "
SELECT schemaname, tablename,
       n_live_tup, n_dead_tup,
       round(n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) * 100, 1) AS dead_pct
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC LIMIT 10;
"

# Manual VACUUM (online, no lock)
docker compose exec db psql -U kaza -d kaza -c "VACUUM ANALYZE orders;"
```

### Redis is down

```bash
# Check status
docker compose exec redis redis-cli ping

# HA: check Sentinel failover
docker compose -f docker-compose.ha.yml exec sentinel1 \
    redis-cli -p 26379 sentinel failover mymaster

# Force failover
docker compose -f docker-compose.ha.yml exec sentinel1 \
    redis-cli -p 26379 sentinel failover mymaster
```

### Circuit breaker is OPEN (CDEK or YooKassa)

When a circuit breaker opens, the API returns `503` for affected endpoints
(CDEK shipping estimates, YooKassa payment creation). Other endpoints are unaffected.

```bash
# Check current circuit breaker state in Redis
docker compose exec redis redis-cli GET "cb:cdek:state"
docker compose exec redis redis-cli GET "cb:yookassa:state"

# Manually reset a stuck OPEN circuit breaker
docker compose exec redis redis-cli DEL "cb:cdek:state" "cb:cdek:failures" "cb:cdek:opened_at"

# Check external API status pages:
# CDEK: https://status.cdek.ru/
# YooKassa: https://status.yookassa.ru/
```

### Rate limit false positives (legitimate users blocked)

```bash
# Check rate limit counters for a specific IP
IP="1.2.3.4"
docker compose exec redis redis-cli KEYS "ratelimit:*${IP}*"

# Clear rate limit for a specific IP (login endpoint)
docker compose exec redis redis-cli DEL "ratelimit:login:${IP}"
```

---

## 11. Scaling

### Horizontal scaling (HA stack)

```bash
# Scale app instances to 4
docker compose -f docker-compose.ha.yml up -d --scale app=4 --no-deps

# Nginx upstream list is static — update deploy/nginx/nginx.ha.conf
# to add app3:8000, app4:8000 and reload Nginx
nginx -s reload
```

### Vertical scaling

```bash
# Add memory/CPU limits in docker-compose.yml under each service:
# deploy:
#   resources:
#     limits:
#       cpus: '2.0'
#       memory: 2G
#     reservations:
#       memory: 512M

# Apply without downtime
docker compose up -d --no-deps app
```

### PgBouncer pool tuning

Edit `deploy/pgbouncer/pgbouncer.ini`:

```ini
# Maximum total client connections across all pools
max_client_conn = 400

# Per-database pool size (matches PostgreSQL max_connections / num_pgbouncer_instances)
default_pool_size = 40

# Reserve connections for admin
reserve_pool_size = 5
reserve_pool_timeout = 3
```

```bash
docker compose -f docker-compose.ha.yml restart pgbouncer
```

---

## 12. Maintenance Mode

Maintenance mode returns `503 Service Unavailable` to all API requests
(except `/health`) while allowing the DB and Redis to stay up.

### Enable maintenance mode

```bash
# Via Redis (takes effect immediately, no restart required)
docker compose exec redis redis-cli SET "maintenance:enabled" "1"

# With optional message shown in the 503 response
docker compose exec redis redis-cli SET "maintenance:message" "We'll be back in 10 minutes — upgrading the database."

# Schedule end time (Unix timestamp)
docker compose exec redis redis-cli SET "maintenance:ends_at" "$(date -d '+30 minutes' +%s)"
```

### Disable maintenance mode

```bash
docker compose exec redis redis-cli DEL "maintenance:enabled" "maintenance:message" "maintenance:ends_at"
```

### Verify maintenance mode is active

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/products/
# Expected: 503
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health
# Expected: 200  (health check bypasses maintenance mode)
```

---

## 13. Common Issues & Fixes

### `alembic.util.exc.CommandError: Can't locate revision`

Migrations are out of sync. Reset the Alembic stamp without running SQL:

```bash
# Check what the DB thinks is the current revision
docker compose exec db psql -U kaza -d kaza -c "SELECT * FROM alembic_version;"

# Stamp to a known good revision (skip the broken one)
docker compose exec app alembic stamp 0022

# Then upgrade from there
docker compose exec app alembic upgrade head
```

### App container exits immediately on startup

```bash
docker compose logs app | tail -30
```

Common causes:
- **`SECRET_KEY` not set** — app refuses to start; set in `.env`
- **DB not ready** — add `depends_on: db: condition: service_healthy` or increase `STARTUP_RETRY_ATTEMPTS`
- **Port 8000 already in use** — `lsof -i :8000`

### `Too many connections` error from PostgreSQL

```bash
# Check current connection count
docker compose exec db psql -U postgres -c \
    "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# Check max_connections setting
docker compose exec db psql -U postgres -c "SHOW max_connections;"

# Force-close idle connections
docker compose exec db psql -U postgres -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
  AND query_start < NOW() - INTERVAL '10 minutes'
  AND pid <> pg_backend_pid();"
```

If persistent, reduce `DB_POOL_SIZE` in `.env` or enable PgBouncer.

### Seller panel `CORS` errors in browser

The API only allows requests from `ALLOWED_ORIGINS` in `.env`.

```bash
# Add the seller panel origin
ALLOWED_ORIGINS=https://panel.example.com,http://localhost:5173
```

Then restart the app: `docker compose restart app`

### Telegram webhook returns 404

```bash
# Check webhook URL matches the route in main.py
docker compose logs app | grep "webhook"

# Re-register webhook with the correct path
curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
     -d "url=https://api.example.com/webhook/${BOT_TOKEN}"
```

### `fernet.InvalidToken` error in logs

The `FERNET_KEY` in `.env` doesn't match the key used to encrypt stored tokens.
See [Section 7 — Fernet Key Rotation](#rotate-fernet_key-bot-token-encryption) for migration procedure.

### Redis Sentinel shows all nodes as `SDOWN`

```bash
# Check if redis-master container is healthy
docker compose -f docker-compose.ha.yml ps redis-master

# Check Sentinel configuration (must match container service names)
docker compose -f docker-compose.ha.yml exec sentinel1 \
    redis-cli -p 26379 info sentinel

# Restart Sentinel nodes (they will re-discover the master)
docker compose -f docker-compose.ha.yml restart sentinel1 sentinel2 sentinel3
```

---

## Quick Reference

| Task | Command |
|---|---|
| Start all services | `docker compose up -d` |
| Stop all services | `docker compose down` |
| View app logs | `docker compose logs -f app` |
| Health check | `curl http://localhost:8000/health` |
| Run migrations | `docker compose exec app alembic upgrade head` |
| Rollback 1 migration | `docker compose exec app alembic downgrade -1` |
| Current migration | `docker compose exec app alembic current` |
| Restart bot | `docker compose restart bot` |
| Enable maintenance | `docker compose exec redis redis-cli SET maintenance:enabled 1` |
| Disable maintenance | `docker compose exec redis redis-cli DEL maintenance:enabled` |
| Run security audit | `bash scripts/security_audit.sh` |
| Create DB backup | `bash backup.sh` |
| Open shell in app | `docker compose exec app bash` |
| Open psql | `docker compose exec db psql -U kaza -d kaza` |
| Open redis-cli | `docker compose exec redis redis-cli` |
