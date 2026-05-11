from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class CacheItem:
    payload: bytes
    expires_at: datetime


class ExportCache:
    """Process-local TTL cache for generated exports."""

    def __init__(self):
        self._lock = threading.Lock()
        self._items: dict[str, CacheItem] = {}

    def get(self, key: str) -> bytes | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            item = self._items.get(key)
            if not item:
                return None
            if item.expires_at <= now:
                self._items.pop(key, None)
                return None
            return item.payload

    def set(self, key: str, payload: bytes, ttl_seconds: int):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(ttl_seconds, 1))
        with self._lock:
            self._items[key] = CacheItem(payload=payload, expires_at=expires_at)

    def prune(self):
        now = datetime.now(timezone.utc)
        with self._lock:
            stale_keys = [k for k, v in self._items.items() if v.expires_at <= now]
            for key in stale_keys:
                self._items.pop(key, None)


export_cache = ExportCache()
