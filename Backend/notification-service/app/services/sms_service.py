"""
Beem Africa SMS integration.
API docs: https://beem.africa/developers/
"""
import os
import httpx
from flask import current_app

BEEM_BASE_URL = "https://apisms.beem.africa/v1"


def send_sms(to: str, message: str) -> bool:
    api_key = os.environ.get("BEEM_API_KEY", "")
    secret_key = os.environ.get("BEEM_SECRET_KEY", "")
    sender_name = os.environ.get("BEEM_SENDER_NAME", "SHEDULEX")

    if not api_key or not secret_key:
        current_app.logger.warning("Beem API credentials not configured. SMS not sent.")
        return False

    payload = {
        "source_addr": sender_name,
        "schedule_time": "",
        "encoding": "0",
        "message": message,
        "recipients": [{"recipient_id": "1", "dest_addr": to}],
    }
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(
                f"{BEEM_BASE_URL}/sendSms",
                json=payload,
                auth=(api_key, secret_key),
            )
            resp.raise_for_status()
            result = resp.json()
            return result.get("successful", False)
    except Exception as exc:
        current_app.logger.error(f"SMS send failed to {to}: {exc}")
        return False


def send_bulk_sms(recipients: list[dict], message: str) -> dict:
    """
    Send SMS to multiple recipients.
    recipients: list of dicts with 'phone' key.
    Returns dict with success/failure counts.
    """
    success_count = 0
    fail_count = 0
    for r in recipients:
        phone = r.get("phone", "")
        if phone:
            if send_sms(phone, message):
                success_count += 1
            else:
                fail_count += 1
    return {"sent": success_count, "failed": fail_count}
