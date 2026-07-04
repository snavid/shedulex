import json
import os
import urllib.error
import urllib.request


def _calendar_url() -> str:
    return os.environ.get("CALENDAR_SERVICE_URL", "http://calendar-service:5005").rstrip("/")


def _internal_key() -> str:
    return os.environ.get("INTERNAL_SERVICE_KEY", "dev-internal-service-key")


def fetch_semester_dates(calendar_semester_id: str) -> dict | None:
    """Return {start_date, end_date} from calendar-service, or None if unavailable."""
    if not calendar_semester_id:
        return None
    url = f"{_calendar_url()}/api/v1/calendar/internal/semesters/{calendar_semester_id}"
    req = urllib.request.Request(
        url,
        headers={"X-Internal-Service-Key": _internal_key()},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            body = json.loads(resp.read().decode())
            data = body.get("data") or {}
            if data.get("start_date") and data.get("end_date"):
                return {
                    "start_date": data["start_date"],
                    "end_date": data["end_date"],
                    "calendar_semester_id": calendar_semester_id,
                }
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, ValueError):
        pass
    return None
