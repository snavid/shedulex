#!/bin/sh
MAX_WAIT=30; i=0
until FLASK_APP=wsgi.py flask db current >/dev/null 2>&1; do
  i=$((i+1)); [ "$i" -ge "$MAX_WAIT" ] && break; sleep 2
done
if FLASK_APP=wsgi.py flask db upgrade; then echo "[entrypoint] Migrations OK."
else
  FLASK_APP=wsgi.py flask db stamp head >/dev/null 2>&1 || true
  FLASK_APP=wsgi.py flask db upgrade    >/dev/null 2>&1 || true
fi
exec gunicorn --bind 0.0.0.0:5004 --workers 1 --timeout 120 wsgi:app
