#!/bin/sh
# Entrypoint for the db-replica container in docker-compose.prod.yml.
# Runs pg_basebackup on first start, then executes postgres in hot-standby mode.
#
# Environment (injected via docker-compose environment section):
#   PGDATA            — replica data directory
#   PRIMARY_HOST      — primary container hostname (default: db)
#   PRIMARY_USER      — replication user (same as DB_USER)
#   PRIMARY_PASSWORD  — replication password (same as DB_PASSWORD)
set -e

PGDATA="${PGDATA:-/var/lib/postgresql/data}"
PRIMARY_HOST="${PRIMARY_HOST:-db}"
PRIMARY_USER="${PRIMARY_USER:-kaza_user}"

# Ensure PGDATA is owned by postgres with restricted permissions
mkdir -p "$PGDATA"
chown postgres:postgres "$PGDATA"
chmod 700 "$PGDATA"

if [ ! -s "$PGDATA/PG_VERSION" ]; then
    echo "[replica] Waiting for primary ${PRIMARY_HOST}..."
    until PGPASSWORD="$PRIMARY_PASSWORD" \
          pg_isready -h "$PRIMARY_HOST" -U "$PRIMARY_USER" 2>/dev/null; do
        sleep 2
    done
    echo "[replica] Running pg_basebackup from ${PRIMARY_HOST}..."
    su-exec postgres \
        env PGPASSWORD="$PRIMARY_PASSWORD" \
        pg_basebackup \
            -h "$PRIMARY_HOST" \
            -U "$PRIMARY_USER" \
            -D "$PGDATA" \
            -Fp -Xs -P -R --checkpoint=fast
    echo "[replica] pg_basebackup complete. Starting in hot-standby mode."
fi

exec su-exec postgres postgres \
    -c hot_standby=on \
    -c max_connections=50 \
    -c shared_buffers=128MB \
    -c effective_cache_size=256MB
