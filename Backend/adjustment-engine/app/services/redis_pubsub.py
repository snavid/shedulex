"""
Redis pub/sub helpers for real-time SSE streaming.

Each agent session gets its own channel: session:<id>:events
Events are both published to the channel (live subscribers) and
appended to a list (for replay when a client connects late).
"""
from __future__ import annotations

import json
import logging
import os

import redis as redis_lib

logger = logging.getLogger(__name__)

_redis_client: redis_lib.Redis | None = None

CHANNEL_PREFIX = "session:"
LOG_TTL        = 3600   # keep event log for 1 hour
LOG_MAX        = 500    # max events stored per session


def get_redis() -> redis_lib.Redis:
    global _redis_client
    if _redis_client is None:
        url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        _redis_client = redis_lib.from_url(url, decode_responses=False)
    return _redis_client


def _channel(session_id: str) -> str:
    return f"{CHANNEL_PREFIX}{session_id}:events"


def _log_key(session_id: str) -> str:
    return f"{CHANNEL_PREFIX}{session_id}:event_log"


def publish(session_id: str, event: dict) -> None:
    """Publish one event to the session's Redis channel + persist to event log."""
    data = json.dumps(event)
    try:
        r = get_redis()
        r.publish(_channel(session_id), data)
        r.rpush(_log_key(session_id), data)
        r.ltrim(_log_key(session_id), -LOG_MAX, -1)
        r.expire(_log_key(session_id), LOG_TTL)
    except Exception as exc:
        logger.warning("Redis publish failed for session %s: %s", session_id, exc)


def get_event_log(session_id: str) -> list[dict]:
    """Return all previously published events (for replay on reconnect)."""
    try:
        r = get_redis()
        raw = r.lrange(_log_key(session_id), 0, -1)
        return [json.loads(item) for item in raw]
    except Exception:
        return []


def clear_event_log(session_id: str) -> None:
    try:
        get_redis().delete(_log_key(session_id))
    except Exception:
        pass


def subscribe(session_id: str):
    """Return a Redis PubSub object subscribed to the session channel."""
    r = get_redis()
    ps = r.pubsub(ignore_subscribe_messages=False)
    ps.subscribe(_channel(session_id))
    return ps
