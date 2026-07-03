import json
import os

import redis
from flask import current_app


def _redis_client() -> redis.Redis:
    url = current_app.config.get(
        "REDIS_URL", os.environ.get("REDIS_URL", "redis://localhost:6490/0")
    )
    return redis.from_url(url, decode_responses=True)


def _events_key(timetable_id: str) -> str:
    return f"timetable_events:{timetable_id}"


def _debounce_key(timetable_id: str) -> str:
    return f"timetable_debounce:{timetable_id}"


def append_event(timetable_id: str, event: dict) -> bool:
    """Append event and return True if a new debounce window was started."""
    client = _redis_client()
    client.rpush(_events_key(timetable_id), json.dumps(event))
    debounce_seconds = int(
        current_app.config.get(
            "TIMETABLE_EVENT_DEBOUNCE_SECONDS",
            os.environ.get("TIMETABLE_EVENT_DEBOUNCE_SECONDS", 300),
        )
    )
    started = client.set(_debounce_key(timetable_id), "1", nx=True, ex=debounce_seconds)
    return bool(started)


def pop_events(timetable_id: str) -> list[dict]:
    client = _redis_client()
    key = _events_key(timetable_id)
    raw_events = client.lrange(key, 0, -1)
    client.delete(key)
    client.delete(_debounce_key(timetable_id))
    events = []
    for raw in raw_events:
        try:
            events.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return events
