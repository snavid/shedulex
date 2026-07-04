"""Fire-and-forget client for the audit-service internal /log endpoint."""

from __future__ import annotations

import json
import os
import threading
import urllib.request

AUDIT_URL = os.environ.get("AUDIT_SERVICE_URL", "http://audit-service:5008")
INTERNAL_KEY = os.environ.get("INTERNAL_SERVICE_KEY", "dev-internal-service-key")

_SKIP_PREFIXES = (
    "/health",
    "/swagger",
    "/api/v1/audit/log",
)

_SKIP_EXACT = {
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
}


def record_audit(
    *,
    service: str,
    action: str,
    user_id: str | None = None,
    university_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    description: str | None = None,
    status: str = "success",
    metadata: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    user_email: str | None = None,
    user_name: str | None = None,
):
    payload = {
        "user_id": user_id,
        "user_email": user_email,
        "user_name": user_name,
        "university_id": university_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "description": description,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "service": service,
        "status": status,
        "metadata": metadata or {},
    }

    def _send():
        try:
            req = urllib.request.Request(
                f"{AUDIT_URL}/api/v1/audit/log",
                data=json.dumps(payload).encode(),
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Key": INTERNAL_KEY,
                },
            )
            urllib.request.urlopen(req, timeout=3)
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()


def _should_skip(path: str) -> bool:
    if path in _SKIP_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in _SKIP_PREFIXES)


def _action_label(method: str, path: str) -> str:
    parts = [p for p in path.strip("/").split("/") if p and p not in ("api", "v1")]
    resource = ".".join(parts[:3]) if parts else path
    return f"{method.lower()}:{resource}"


def _resource_from_path(path: str) -> tuple[str | None, str | None]:
    parts = [p for p in path.strip("/").split("/") if p and p not in ("api", "v1")]
    if len(parts) >= 2 and parts[-1] not in (
        "create", "activate", "approve", "reject", "refresh", "logout",
        "register", "login", "subscribe", "session", "generate", "publish",
    ):
        return parts[0], parts[-1]
    if parts:
        return parts[0], None
    return None, None


def register_audit_middleware(app, service_name: str):
    """Log mutating API requests after the response is ready."""

    @app.after_request
    def _audit_after_request(response):
        from flask import request

        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return response

        path = request.path or ""
        if _should_skip(path):
            return response

        user_id = None
        university_id = None
        user_email = None
        user_name = None
        role = None
        try:
            from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

            verify_jwt_in_request(optional=True)
            user_id = get_jwt_identity()
            claims = get_jwt()
            university_id = claims.get("university_id")
            user_email = claims.get("email")
            user_name = claims.get("email")
            role = claims.get("role")
        except Exception:
            pass

        status = "success" if response.status_code < 400 else "failure"
        resource_type, resource_id = _resource_from_path(path)

        record_audit(
            service=service_name,
            action=_action_label(request.method, path),
            user_id=user_id,
            user_email=user_email,
            user_name=user_name,
            university_id=university_id,
            resource_type=resource_type,
            resource_id=resource_id,
            description=f"{request.method} {path} → HTTP {response.status_code}",
            status=status,
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent", "")[:500],
            metadata={
                "method": request.method,
                "path": path,
                "status_code": response.status_code,
                "role": role,
            },
        )
        return response
