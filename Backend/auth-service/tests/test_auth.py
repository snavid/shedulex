import pytest


class TestRegister:
    def test_register_success(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "newuser@test.com",
            "username": "newuser",
            "password": "Secure1234",
            "first_name": "New",
            "last_name": "User",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["success"] is True
        assert "access_token" in data["data"]

    def test_register_duplicate_email(self, client):
        payload = {
            "email": "dup@test.com", "username": "dup1",
            "password": "Secure1234", "first_name": "A", "last_name": "B",
        }
        client.post("/api/v1/auth/register", json=payload)
        payload["username"] = "dup2"
        resp = client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 409

    def test_register_weak_password(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "weak@test.com", "username": "weakpw",
            "password": "password", "first_name": "A", "last_name": "B",
        })
        assert resp.status_code == 422

    def test_register_invalid_email(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "not-an-email", "username": "user123",
            "password": "Secure1234", "first_name": "A", "last_name": "B",
        })
        assert resp.status_code == 422


class TestLogin:
    def test_login_success(self, client, admin_user):
        resp = client.post("/api/v1/auth/login", json={
            "email": "admin@test.com", "password": "Admin1234",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "access_token" in data["data"]

    def test_login_wrong_password(self, client, admin_user):
        resp = client.post("/api/v1/auth/login", json={
            "email": "admin@test.com", "password": "WrongPass1",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "email": "nobody@test.com", "password": "Secure1234",
        })
        assert resp.status_code == 401


class TestMe:
    def test_me_returns_user(self, client, admin_user):
        login_resp = client.post("/api/v1/auth/login", json={
            "email": "admin@test.com", "password": "Admin1234",
        })
        token = login_resp.get_json()["data"]["access_token"]
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.get_json()["data"]["email"] == "admin@test.com"

    def test_me_without_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401


class TestLogout:
    def test_logout_success(self, client, admin_user):
        login_resp = client.post("/api/v1/auth/login", json={
            "email": "admin@test.com", "password": "Admin1234",
        })
        token = login_resp.get_json()["data"]["access_token"]
        resp = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
