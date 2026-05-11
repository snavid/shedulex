from app.services.export_security import decode_share_token


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_create_share_link_manager_success(client, app, make_access_token):
    token = make_access_token(role="admin")
    resp = client.post(
        "/api/v1/documents/share-links",
        headers=_auth_header(token),
        json={"timetable_id": "tt-123", "format": "pdf", "expires_hours": 12},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["success"] is True
    data = body["data"]
    assert data["timetable_id"] == "tt-123"
    assert data["format"] == "pdf"
    assert "/api/v1/documents/share/" in data["download_url"]
    with app.app_context():
        payload = decode_share_token(data["token"])
    assert payload["tid"] == "tt-123"
    assert payload["fmt"] == "pdf"


def test_create_share_link_supports_role_list(client, make_access_token):
    token = make_access_token(role=None, roles=["lecturer", "hod"])
    resp = client.post(
        "/api/v1/documents/share-links",
        headers=_auth_header(token),
        json={"timetable_id": "tt-456", "format": "bundle", "expires_hours": 24},
    )
    assert resp.status_code == 201
    assert resp.get_json()["success"] is True


def test_create_share_link_forbidden_for_non_manager(client, make_access_token):
    token = make_access_token(role="student")
    resp = client.post(
        "/api/v1/documents/share-links",
        headers=_auth_header(token),
        json={"timetable_id": "tt-123", "format": "pdf", "expires_hours": 12},
    )
    assert resp.status_code == 403
    assert resp.get_json()["success"] is False


def test_create_share_link_rejects_non_integer_expiry(client, make_access_token):
    token = make_access_token(role="admin")
    resp = client.post(
        "/api/v1/documents/share-links",
        headers=_auth_header(token),
        json={"timetable_id": "tt-123", "format": "pdf", "expires_hours": "abc"},
    )
    assert resp.status_code == 422
    body = resp.get_json()
    assert body["success"] is False
    assert "must be an integer" in body["message"]


def test_shared_download_rejects_invalid_token(client):
    resp = client.get("/api/v1/documents/share/not-a-valid-token")
    assert resp.status_code == 401
    assert resp.get_json()["success"] is False


def test_preview_returns_safe_error_payload_on_failure(client, make_access_token, monkeypatch):
    token = make_access_token(role="admin")

    def _raise(_timetable_id):
        raise RuntimeError("upstream exploded")

    monkeypatch.setattr("app.routes.documents.preview_exports", _raise)
    resp = client.get("/api/v1/documents/timetable/tt-123/preview", headers=_auth_header(token))
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert body["message"] == "Failed to load export preview."
