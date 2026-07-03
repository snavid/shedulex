import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app

LOCAL_TZ = ZoneInfo("Africa/Dar_es_Salaam")


def _notification_url() -> str:
    return os.environ.get("NOTIFICATION_SERVICE_URL", "http://notification-service:5004")


def _internal_key() -> str:
    return os.environ.get("INTERNAL_SERVICE_KEY", "dev-internal-service-key")


def _post_event(payload: dict) -> None:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{_notification_url()}/api/v1/notifications/internal/calendar-event",
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Internal-Service-Key": _internal_key(),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            resp.read()
    except Exception as exc:
        try:
            current_app.logger.warning("Failed to emit calendar notification: %s", exc)
        except Exception:
            pass


def maybe_notify_same_day_event(event_dict: dict) -> None:
    """Notify immediately when announcement/emergency events are created for today."""
    if event_dict.get("event_type") not in ("announcement", "emergency"):
        return
    try:
        start = event_dict.get("start") or ""
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        if start_dt.astimezone(LOCAL_TZ).date() != datetime.now(LOCAL_TZ).date():
            return
    except Exception:
        return
    thread = threading.Thread(target=_post_event, args=(event_dict,), daemon=True)
    thread.start()
