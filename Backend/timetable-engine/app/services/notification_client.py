import json
import os
import threading
import urllib.error
import urllib.request

from flask import current_app


def _notification_url() -> str:
    return os.environ.get("NOTIFICATION_SERVICE_URL", "http://notification-service:5004")


def _internal_key() -> str:
    return os.environ.get("INTERNAL_SERVICE_KEY", "dev-internal-service-key")


def _notify_enabled() -> bool:
    return os.environ.get("TIMETABLE_NOTIFY_ENABLED", "true").lower() == "true"


def _log_warning(message: str, *args) -> None:
    try:
        current_app.logger.warning(message, *args)
    except Exception:
        pass


def _post_event(payload: dict, *, attempt: int = 1) -> None:
    if not _notify_enabled():
        return
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{_notification_url()}/api/v1/notifications/internal/timetable-event",
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Internal-Service-Key": _internal_key(),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode()
            if resp.status >= 400:
                _log_warning(
                    "Timetable notification event returned %s: %s payload=%s",
                    resp.status,
                    body,
                    payload.get("event_type"),
                )
    except Exception as exc:
        _log_warning(
            "Failed to emit timetable notification event (attempt %s): %s payload=%s",
            attempt,
            exc,
            payload.get("event_type"),
        )
        if attempt == 1:
            _post_event(payload, attempt=2)


def emit_timetable_event(payload: dict) -> None:
    """Fire-and-forget POST to notification-service."""
    thread = threading.Thread(target=_post_event, args=(payload,), daemon=True)
    thread.start()
