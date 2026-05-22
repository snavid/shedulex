#!/bin/sh
echo "[entrypoint] Waiting for postgres..."
MAX_WAIT=30
i=0
until FLASK_APP=wsgi.py flask db current >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -ge "$MAX_WAIT" ]; then echo "[entrypoint] DB wait timed out, proceeding."; break; fi
  echo "[entrypoint] DB not ready (${i}/${MAX_WAIT}), retrying in 2s..."
  sleep 2
done
if FLASK_APP=wsgi.py flask db upgrade; then echo "[entrypoint] Migrations OK."
else
  FLASK_APP=wsgi.py flask db stamp head >/dev/null 2>&1 || true
  FLASK_APP=wsgi.py flask db upgrade    >/dev/null 2>&1 || true
fi
exec gunicorn --bind 0.0.0.0:5003 --workers 1 --timeout 180 wsgi:app
