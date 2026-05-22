#!/bin/sh
# No global set -e — migration failures must not kill gunicorn.

echo "[entrypoint] Waiting for postgres..."
MAX_WAIT=30
i=0
until FLASK_APP=wsgi.py flask db current >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -ge "$MAX_WAIT" ]; then
    echo "[entrypoint] DB wait timed out after ${MAX_WAIT}s, proceeding anyway."
    break
  fi
  echo "[entrypoint] DB not ready (${i}/${MAX_WAIT}), retrying in 2s..."
  sleep 2
done

echo "[entrypoint] Running migrations..."
if FLASK_APP=wsgi.py flask db upgrade; then
  echo "[entrypoint] Migrations OK."
else
  echo "[entrypoint] flask db upgrade failed — stamping head and retrying once..."
  FLASK_APP=wsgi.py flask db stamp head >/dev/null 2>&1 || true
  FLASK_APP=wsgi.py flask db upgrade    >/dev/null 2>&1 || echo "[entrypoint] Retry also failed — starting with existing schema."
fi

echo "[entrypoint] Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:5002 --workers 1 --timeout 300 wsgi:app
