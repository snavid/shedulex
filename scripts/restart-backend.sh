#!/usr/bin/env bash
# Rebuild/restart backend services and refresh Kong upstream DNS.
#
# Usage (from project root):
#   bash scripts/restart-backend.sh timetable-engine
#   bash scripts/restart-backend.sh notification-service notification-worker notification-beat
#
# After any backend container is recreated, Kong must be restarted so it
# stops routing to stale Docker IPs.
set -e

if [ "$#" -eq 0 ]; then
  echo "Usage: bash scripts/restart-backend.sh <service> [service...]"
  exit 1
fi

docker compose up -d "$@"
docker compose restart kong

echo ""
echo "Services restarted and Kong reloaded."
echo "Portal/API: http://localhost:8000"
