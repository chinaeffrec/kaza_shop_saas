#!/bin/bash
# Initialises a PostgreSQL streaming replica from the primary using pg_basebackup.
# Runs inside the pg-replica container as the postgres user.
#
# Environment variables (injected by docker-compose):
#   PRIMARY_HOST      — hostname of the primary (e.g. pg-primary)
#   PRIMARY_USER      — replication user (same as app user for simplicity)
#   PRIMARY_PASSWORD  — password
#   PGDATA            — data directory (e.g. /var/lib/postgresql/data)

set -euo pipefail

PRIMARY_HOST="${PRIMARY_HOST:-pg-primary}"
PRIMARY_USER="${PRIMARY_USER:-kaza}"
PRIMARY_PASSWORD="${PRIMARY_PASSWORD}"
PGDATA="${PGDATA:-/var/lib/postgresql/data}"

# If data directory already has a PG_VERSION file, the replica is already
# initialised — skip to avoid overwriting on restart.
if [ -f "${PGDATA}/PG_VERSION" ]; then
    echo "[init-replica] Data directory already exists, skipping pg_basebackup."
    exit 0
fi

echo "[init-replica] Waiting for primary ${PRIMARY_HOST} to be ready..."
until PGPASSWORD="${PRIMARY_PASSWORD}" pg_isready -h "${PRIMARY_HOST}" -U "${PRIMARY_USER}" -d kazadb; do
    echo "[init-replica] Primary not ready — sleeping 2s..."
    sleep 2
done

echo "[init-replica] Running pg_basebackup from ${PRIMARY_HOST}..."
PGPASSWORD="${PRIMARY_PASSWORD}" pg_basebackup \
    -h "${PRIMARY_HOST}" \
    -U "${PRIMARY_USER}" \
    -D "${PGDATA}" \
    -Fp \
    -Xs \
    -P \
    -R

# -Fp  = plain format (copy files directly)
# -Xs  = stream WAL during backup
# -P   = progress output
# -R   = write recovery.conf / standby.signal + postgresql.auto.conf

echo "[init-replica] pg_basebackup complete. Replica is ready."
