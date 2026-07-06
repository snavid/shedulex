#!/usr/bin/env bash
# Build and start the full Shedulex stack in production mode (Kong on localhost).
#
# Usage (from project root):
#   bash scripts/deploy-production.sh
#   bash scripts/deploy-production.sh --no-build
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
NO_BUILD=false
for arg in "$@"; do
  if [ "$arg" = "--no-build" ]; then NO_BUILD=true; fi
done

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.production.example to .env and fill in secrets."
  exit 1
fi

echo "==> Starting Shedulex (production compose)..."
if [ "$NO_BUILD" = true ]; then
  $COMPOSE up -d
else
  $COMPOSE up -d --build
fi

echo "==> Restarting Kong (refresh upstream DNS)..."
$COMPOSE restart kong

echo ""
echo "Waiting for Kong health..."
sleep 5
if curl -sf http://127.0.0.1:8000/api/v1/universities >/dev/null 2>&1; then
  echo "Kong proxy OK: http://127.0.0.1:8000"
else
  echo "WARN: Kong health check via localhost:8000 failed — check: $COMPOSE logs kong"
fi

echo ""
echo "Deploy complete."
echo "  Local Kong:  http://127.0.0.1:8000"
echo "  Public API:  https://shedulex.hudumatech.com/api/v1"
echo "  Ensure Nginx site is enabled: deploy/nginx/shedulex.conf"
