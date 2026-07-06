#!/usr/bin/env bash
# Restore Shedulex Postgres from a pg_dumpall file.
#
# Usage (from project root, postgres container must be running):
#   bash scripts/restore.sh backups/shedulex-YYYYMMDD-HHMMSS/postgres-all.sql
#
# Optional prod compose:
#   COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml" bash scripts/restore.sh ...
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: bash scripts/restore.sh <path-to-postgres-all.sql>"
  exit 1
fi

DUMP="$1"
if [ ! -f "$DUMP" ]; then
  echo "ERROR: dump file not found: $DUMP"
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PG_CONTAINER="${PG_CONTAINER:-shedulex-postgres}"
COMPOSE_FILES="${COMPOSE_FILES:--f docker-compose.yml}"

if [ -f .env ]; then
  _pu="$(grep -E '^POSTGRES_USER=' .env | head -1 | cut -d= -f2- | tr -d '\r\n' | sed 's/^["'"'"']//; s/["'"'"']$//')"
  [ -n "$_pu" ] && POSTGRES_USER="$_pu"
  unset _pu
fi
PG_USER="${POSTGRES_USER:-shedulex}"

if ! docker inspect "$PG_CONTAINER" >/dev/null 2>&1; then
  echo "ERROR: container $PG_CONTAINER not found."
  echo "Start it first: docker compose $COMPOSE_FILES up -d postgres"
  exit 1
fi

if ! docker exec "$PG_CONTAINER" pg_isready -U "$PG_USER" -d shedulex_master >/dev/null 2>&1; then
  echo "ERROR: postgres is not ready."
  echo "Start it first: docker compose $COMPOSE_FILES up -d postgres"
  exit 1
fi

echo "==> Restoring from: $DUMP"
echo "    WARNING: This replaces all databases in the Postgres instance."
read -r -p "Continue? [y/N] " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
  echo "Aborted."
  exit 0
fi

docker exec -i "$PG_CONTAINER" psql -U "$PG_USER" -d postgres < "$DUMP"

echo ""
echo "Restore complete."
echo "Next: bash scripts/deploy-production.sh"
