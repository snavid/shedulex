"""
Beem Africa SMS integration.
API docs: https://beem.africa/developers/
"""
import base64
import json
import os
import re

import requests
from flask import current_app

URL = "https://apisms.beem.africa/v1/send"
CONTENT_TYPE = "application/json"


def normalize_phone(phone: str | None) -> str:
    """Strip whitespace and leading + for Beem dest_addr."""
    if not phone:
        return ""
    cleaned = re.sub(r"\s+", "", phone.strip())
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    return cleaned


def _beem_config() -> tuple[str, str, str]:
    cfg = current_app.config if current_app else {}
    api_key = cfg.get("BEEM_API_KEY") or os.getenv("BEEM_API_KEY", "")
    secret_key = cfg.get("BEEM_SECRET_KEY") or os.getenv("BEEM_SECRET_KEY", "")
    source_addr = cfg.get("BEEM_SENDER_NAME") or os.getenv("BEEM_SENDER_NAME", "HudumaTech")
    return api_key, secret_key, source_addr


def _format_beem_error(status_code: int, response_text: str) -> str:
    """Return a human-readable Beem API error for UI and logs."""
    text = (response_text or "").strip()
    if text:
        try:
            body = json.loads(text)
            message = body.get("message")
            code = body.get("code")
            data = body.get("data")
            if isinstance(data, dict):
                message = message or data.get("message")
                error_code = data.get("error_code")
                if message and error_code:
                    return f"Beem: {message} ({status_code}, {error_code})"
            if message:
                if code is not None:
                    return f"Beem: {message} ({status_code}, code {code})"
                return f"Beem: {message} ({status_code})"
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass
    return f"Beem SMS failed (HTTP {status_code})"


def send_sms(phone_number: str, message: str) -> tuple[bool, str | None]:
    """
    Send an SMS using the Beem SMS gateway API v1.
    Returns (success, error_detail).
    """
    api_key, secret_key, source_addr = _beem_config()
    dest_addr = normalize_phone(phone_number)

    if not api_key or not secret_key:
        detail = "BEEM credentials are missing. Set BEEM_API_KEY and BEEM_SECRET_KEY in .env."
        current_app.logger.error(detail)
        return False, detail

    if not dest_addr:
        detail = "SMS destination phone number is empty."
        current_app.logger.error(detail)
        return False, detail

    response = None
    payload = {
        "source_addr": source_addr,
        "encoding": 0,
        "schedule_time": "",
        "message": message,
        "recipients": [
            {"recipient_id": "1", "dest_addr": dest_addr}
        ],
    }
    auth_value = base64.b64encode(f"{api_key}:{secret_key}".encode("utf-8")).decode("utf-8")
    headers = {
        "Content-Type": CONTENT_TYPE,
        "Authorization": f"Basic {auth_value}",
    }
    try:
        response = requests.post(
            url=URL,
            data=json.dumps(payload),
            headers=headers,
            timeout=10,
        )
        if response.ok:
            return True, None
        detail = _format_beem_error(response.status_code, response.text)
        current_app.logger.error(
            "Beem SMS failed for %s: %s %s",
            dest_addr,
            response.status_code,
            response.text.strip() or detail,
        )
        return False, detail
    except requests.exceptions.SSLError as ssl_err:
        detail = f"SSL Error: {ssl_err}"
        current_app.logger.error(detail)
        return False, detail
    except requests.exceptions.RequestException as exc:
        detail = str(exc)
        current_app.logger.error("Error sending SMS to %s: %s", dest_addr, exc)
        return False, detail
    except Exception as exc:
        detail = str(exc)
        current_app.logger.error("Unexpected SMS error: %s", exc)
        return False, detail
    finally:
        if response is not None:
            current_app.logger.info("SMS API response status: %s", response.status_code)


def send_bulk_sms(recipients: list[dict], message: str) -> dict:
    """
    Send SMS to multiple recipients.
    recipients: list of dicts with 'phone' key.
    Returns dict with success/failure counts.
    """
    success_count = 0
    fail_count = 0
    for recipient in recipients:
        phone = recipient.get("phone", "")
        if phone:
            ok, _ = send_sms(phone, message)
            if ok:
                success_count += 1
            else:
                fail_count += 1
    return {"sent": success_count, "failed": fail_count}
