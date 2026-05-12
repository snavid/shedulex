"""HTTP client for timetable-engine snapshot API (internal service key)."""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

TIMETABLE_URL = os.environ.get("TIMETABLE_SERVICE_URL", "http://timetable-engine:5002")
INTERNAL_KEY = os.environ.get("INTERNAL_SERVICE_KEY", "dev-internal-service-key")


def create_timetable_snapshot(timetable_id: str, notes: str, created_by: str) -> bool:
    """POST /api/v1/timetable/<id>/versions. Returns True on success."""
    url = f"{TIMETABLE_URL}/api/v1/timetable/{timetable_id}/versions"
    headers = {"X-Internal-Service-Key": INTERNAL_KEY, "Content-Type": "application/json"}
    payload = {"notes": (notes or "")[:500], "created_by": (created_by or "adjustment-engine")[:80]}
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("timetable snapshot failed for %s: %s", timetable_id, exc)
        return False
