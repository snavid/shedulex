from datetime import datetime, timedelta, timezone

import pytest

from app.services.export_cache import ExportCache
from app.services.export_security import create_share_token, decode_share_token


def test_export_cache_set_get_and_expire():
    cache = ExportCache()
    cache.set("k1", b"payload", ttl_seconds=30)
    assert cache.get("k1") == b"payload"

    cache._items["k1"].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert cache.get("k1") is None


def test_export_cache_prune_removes_stale_entries():
    cache = ExportCache()
    cache.set("fresh", b"a", ttl_seconds=30)
    cache.set("stale", b"b", ttl_seconds=30)
    cache._items["stale"].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    cache.prune()

    assert "stale" not in cache._items
    assert "fresh" in cache._items


def test_share_token_roundtrip(app):
    with app.app_context():
        token, _ = create_share_token(
            timetable_id="tt-789",
            export_format="bundle",
            expires_hours=1,
            issued_by="admin-user",
        )
        payload = decode_share_token(token)

    assert payload["tid"] == "tt-789"
    assert payload["fmt"] == "bundle"
    assert payload["iss"] == "admin-user"


def test_share_token_invalid_signature_raises(app):
    with app.app_context():
        with pytest.raises(ValueError, match="Invalid share token"):
            decode_share_token("not-a-valid-token")
