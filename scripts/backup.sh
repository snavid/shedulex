#!/usr/bin/env bash
# Backup Shedulex Postgres, .env, and optional Chroma volume.
#
# Usage (from project root):
#   bash scripts/backup.sh
#   bash scripts/backup.sh --with-chroma
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PG_CONTAINER="${PG_CONTAINER:-shedulex-postgres}"

# Read POSTGRES_USER from .env without sourcing (Windows CRLF-safe)
if [ -f .env ]; then
  _pu="$(grep -E '^POSTGRES_USER=' .env | head -1 | cut -d= -f2- | tr -d '\r\n' | sed 's/^["'"'"']//; s/["'"'"']$//')"
  [ -n "$_pu" ] && POSTGRES_USER="$_pu"
  unset _pu
fi
PG_USER="${POSTGRES_USER:-shedulex}"

wait_for_postgres() {
  local max_attempts="${1:-30}"
  local attempt=0

  if ! docker inspect "$PG_CONTAINER" >/dev/null 2>&1; then
    echo "==> Postgres container not found — starting via compose..."
    docker compose up -d postgres
  elif [ "$(docker inspect -f '{{.State.Running}}' "$PG_CONTAINER" 2>/dev/null)" != "true" ]; then
    echo "==> Postgres container stopped — starting..."
    docker start "$PG_CONTAINER" 2>/dev/null || docker compose up -d postgres
  fi

  echo "==> Waiting for Postgres ($PG_CONTAINER)..."
  while [ "$attempt" -lt "$max_attempts" ]; do
    if docker exec "$PG_CONTAINER" pg_isready -U "$PG_USER" -d shedulex_master >/dev/null 2>&1; then
      echo "==> Postgres is ready."
      return 0
    fi
    attempt=$((attempt + 1))
    sleep 2
  done
  return 1
}

WITH_CHROMA=false
for arg in "$@"; do
  if [ "$arg" = "--with-chroma" ]; then
    WITH_CHROMA=true
  fi
done

STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="backups/shedulex-${STAMP}"
mkdir -p "$DEST"

echo "==> Backup directory: $DEST"

echo "==> Checking Docker..."
if command -v timeout >/dev/null 2>&1; then
  if ! timeout 20 docker info >/dev/null 2>&1; then
    echo "ERROR: Docker is not responding (timed out after 20s)."
    echo "  Start Docker Desktop and wait until the engine is running, then retry."
    exit 1
  fi
elif ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker is not running. Start Docker Desktop and retry."
  exit 1
fi

if ! wait_for_postgres 30; then
  echo "ERROR: postgres did not become ready within 60s."
  echo "  Check: docker ps -a --filter name=$PG_CONTAINER"
  echo "  Start: docker compose up -d postgres"
  exit 1
fi

echo "==> Dumping all Postgres databases..."
docker exec "$PG_CONTAINER" pg_dumpall -U "$PG_USER" -c > "$DEST/postgres-all.sql"
chmod 600 "$DEST/postgres-all.sql" 2>/dev/null || true

if [ -f .env ]; then
  cp .env "$DEST/env.backup"
  chmod 600 "$DEST/env.backup" 2>/dev/null || true
  echo "==> Copied .env to env.backup"
else
  echo "WARN: no .env file found — skipping env backup"
fi

if [ "$WITH_CHROMA" = true ]; then
  echo "==> Archiving chroma_data volume (may take a minute)..."
  VOLUME="$(docker volume ls -q | grep chroma_data | head -1)"
  if [ -n "$VOLUME" ]; then
    docker run --rm \
      -v "${VOLUME}:/data:ro" \
      -v "${ROOT}/${DEST}:/backup" \
      alpine tar czf /backup/chroma-data.tar.gz -C /data .
    echo "==> chroma-data.tar.gz written"
  else
    echo "WARN: chroma_data volume not found — skipping"
  fi
fi

{
  echo "timestamp=$STAMP"
  echo "host=$(hostname 2>/dev/null || echo unknown)"
  if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "git_commit=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
    echo "git_branch=$(git branch --show-current 2>/dev/null || echo unknown)"
  fi
  echo ""
  echo "=== docker ps (postgres) ==="
  docker ps -a --filter "name=$PG_CONTAINER" 2>/dev/null || true
} > "$DEST/manifest.txt"

BYTES="$(wc -c < "$DEST/postgres-all.sql" | tr -d ' ')"
if [ "$BYTES" -lt 1000 ]; then
  echo "ERROR: postgres-all.sql looks too small (${BYTES} bytes). Aborting."
  exit 1
fi

echo ""
echo "Backup complete: $DEST"
echo "  postgres-all.sql  (${BYTES} bytes)"
echo "  manifest.txt"
[ -f "$DEST/env.backup" ] && echo "  env.backup"
[ -f "$DEST/chroma-data.tar.gz" ] && echo "  chroma-data.tar.gz"
