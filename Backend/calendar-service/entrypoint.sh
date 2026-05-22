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
echo "[entrypoint] Running migrations..."
if FLASK_APP=wsgi.py flask db upgrade; then
  echo "[entrypoint] Migrations OK."
else
  echo "[entrypoint] Migration failed — stamping head and retrying..."
  FLASK_APP=wsgi.py flask db stamp head >/dev/null 2>&1 || true
  FLASK_APP=wsgi.py flask db upgrade    >/dev/null 2>&1 || echo "[entrypoint] Retry failed — starting with existing schema."
fi
exec gunicorn --bind 0.0.0.0:5005 --workers 1 wsgi:app
