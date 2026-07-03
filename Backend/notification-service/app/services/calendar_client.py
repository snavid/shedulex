import os

import httpx
from flask import current_app


def _base_url() -> str:
    return current_app.config.get(
        "CALENDAR_SERVICE_URL",
        os.environ.get("CALENDAR_SERVICE_URL", "http://calendar-service:5005"),
    )


def _headers() -> dict:
    return {
        "X-Internal-Service-Key": current_app.config.get(
            "INTERNAL_SERVICE_KEY", os.environ.get("INTERNAL_SERVICE_KEY", "")
        ),
    }


def fetch_today_events(university_id: str | None = None) -> list[dict]:
    params = {}
    if university_id:
        params["university_id"] = university_id
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                f"{_base_url()}/api/v1/calendar/internal/events/today",
                params=params,
                headers=_headers(),
            )
            if resp.status_code != 200:
                current_app.logger.error("Calendar today events failed: %s", resp.text)
                return []
            return resp.json().get("data") or []
    except Exception as exc:
        current_app.logger.error("Calendar fetch error: %s", exc)
        return []
