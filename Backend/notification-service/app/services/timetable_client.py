import os

import httpx
from flask import current_app


def _headers() -> dict:
    return {
        "X-Internal-Service-Key": current_app.config.get(
            "INTERNAL_SERVICE_KEY", os.environ.get("INTERNAL_SERVICE_KEY", "")
        ),
    }


def _base_url() -> str:
    return current_app.config.get(
        "TIMETABLE_SERVICE_URL",
        os.environ.get("TIMETABLE_SERVICE_URL", "http://timetable-engine:5002"),
    )


def get_timetable(timetable_id: str) -> dict | None:
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                f"{_base_url()}/api/v1/timetable/{timetable_id}",
                headers=_headers(),
            )
            if resp.status_code != 200:
                return None
            return resp.json().get("data")
    except Exception as exc:
        current_app.logger.error("Failed to fetch timetable %s: %s", timetable_id, exc)
        return None


def get_timetable_entries(timetable_id: str) -> list[dict]:
    timetable = get_timetable(timetable_id)
    if not timetable:
        return []
    return timetable.get("entries") or []
