import json
import os
import urllib.error
import urllib.request

AUTH_URL = os.environ.get("AUTH_SERVICE_URL", "http://auth-service:5001")
INTERNAL_KEY = os.environ.get("INTERNAL_SERVICE_KEY", "")


def lookup_users(user_ids: list[str]) -> dict[str, dict]:
    """Resolve user ids to display info via auth-service internal API."""
    ids = [uid for uid in user_ids if uid]
    if not ids:
        return {}

    payload = json.dumps({"ids": ids}).encode()
    req = urllib.request.Request(
        f"{AUTH_URL}/api/v1/users/internal/batch",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Internal-Service-Key": INTERNAL_KEY,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            return body.get("data") or {}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {}
