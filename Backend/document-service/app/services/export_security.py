from __future__ import annotations

import time
from datetime import datetime, timezone

from flask import current_app
from itsdangerous import BadSignature, URLSafeSerializer


def _serializer() -> URLSafeSerializer:
    secret_key = current_app.config["DOCUMENT_SHARE_SECRET"]
    salt = current_app.config["DOCUMENT_SHARE_SALT"]
    return URLSafeSerializer(secret_key=secret_key, salt=salt)


def create_share_token(*, timetable_id: str, export_format: str, expires_hours: int, issued_by: str | None) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    expires_ts = int(now.timestamp()) + max(1, expires_hours) * 3600
    payload = {
        "tid": timetable_id,
        "fmt": export_format,
        "exp": expires_ts,
        "iss": issued_by,
    }
    token = _serializer().dumps(payload)
    return token, datetime.fromtimestamp(expires_ts, tz=timezone.utc).isoformat()


def decode_share_token(token: str) -> dict:
    try:
        payload = _serializer().loads(token)
    except BadSignature as exc:
        raise ValueError("Invalid share token.") from exc

    exp_ts = int(payload.get("exp", 0))
    if exp_ts <= int(time.time()):
        raise ValueError("Share token has expired.")

    required = ("tid", "fmt", "exp")
    for field in required:
        if field not in payload:
            raise ValueError("Malformed share token.")

    return payload
