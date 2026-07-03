import pytest


class TestRegister:
    def test_register_success(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "newuser@test.com",
            "username": "newuser",
            "password": "Secure1234",
            "first_name": "New",
            "last_name": "User",
            "phone": "+255700000001",
            "role_name": "admin",
            "university_name": "Test Uni",
            "university_code": "TU",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["success"] is True
        assert "access_token" in data["data"]

    def test_register_missing_phone(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "nophone@test.com",
            "username": "nophone",
            "password": "Secure1234",
            "first_name": "No",
            "last_name": "Phone",
            "role_name": "student",
            "program_id": "prog-1",
        })
        assert resp.status_code == 422

    def test_register_duplicate_email(self, client):
        payload = {
            "email": "dup@test.com", "username": "dup1",
            "password": "Secure1234", "first_name": "A", "last_name": "B",
            "phone": "+255700000002",
            "program_id": "prog-1",
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


def _login(client, email, password):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.get_json()["data"]["access_token"]


class TestUpdateUser:
    def test_user_updates_own_email_and_phone(self, client, admin_user):
        token = _login(client, "admin@test.com", "Admin1234")
        resp = client.patch(
            f"/api/v1/users/{admin_user.id}",
            json={"email": "admin.updated@test.com", "phone": "+255700000099"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["email"] == "admin.updated@test.com"
        assert data["phone"] == "+255700000099"

    def test_admin_updates_other_user_contact(self, client, db, admin_user):
        from app.models.user import User, Role

        role = Role.query.filter_by(name="lecturer").first()
        other = User(
            email="lect@test.com",
            username="lectuser",
            first_name="Lect",
            last_name="User",
            phone="+255700000010",
            role_id=role.id,
            is_verified=True,
            university_id=admin_user.university_id,
        )
        other.set_password("Secure1234")
        db.session.add(other)
        db.session.commit()

        token = _login(client, "admin@test.com", "Admin1234")
        resp = client.patch(
            f"/api/v1/users/{other.id}",
            json={"email": "lect.updated@test.com", "phone": "+255700000011"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["email"] == "lect.updated@test.com"
        assert data["phone"] == "+255700000011"

    def test_duplicate_email_returns_409(self, client, db, admin_user):
        from app.models.user import User, Role

        role = Role.query.filter_by(name="student").first()
        other = User(
            email="taken@test.com",
            username="takenuser",
            first_name="Taken",
            last_name="User",
            phone="+255700000020",
            role_id=role.id,
            is_verified=True,
        )
        other.set_password("Secure1234")
        db.session.add(other)
        db.session.commit()

        token = _login(client, "admin@test.com", "Admin1234")
        resp = client.patch(
            f"/api/v1/users/{admin_user.id}",
            json={"email": "taken@test.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409

    def test_non_admin_cannot_update_other_user(self, client, db):
        from app.models.user import User, Role

        role = Role.query.filter_by(name="lecturer").first()
        user_a = User(
            email="usera@test.com",
            username="usera",
            first_name="User",
            last_name="A",
            phone="+255700000030",
            role_id=role.id,
            is_verified=True,
        )
        user_b = User(
            email="userb@test.com",
            username="userb",
            first_name="User",
            last_name="B",
            phone="+255700000031",
            role_id=role.id,
            is_verified=True,
        )
        for u in (user_a, user_b):
            u.set_password("Secure1234")
            db.session.add(u)
        db.session.commit()

        token = _login(client, "usera@test.com", "Secure1234")
        resp = client.patch(
            f"/api/v1/users/{user_b.id}",
            json={"phone": "+255700000099"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_phone_with_at_rejected(self, client, admin_user):
        token = _login(client, "admin@test.com", "Admin1234")
        resp = client.patch(
            f"/api/v1/users/{admin_user.id}",
            json={"phone": "bad@email.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422
        errors = resp.get_json()["errors"]
        assert "phone" in errors

    def test_partial_email_update_keeps_phone(self, client, admin_user):
        admin_user.phone = "+255700000088"
        from app.extensions import db
        db.session.commit()

        token = _login(client, "admin@test.com", "Admin1234")
        resp = client.patch(
            f"/api/v1/users/{admin_user.id}",
            json={"email": "admin.partial@test.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["email"] == "admin.partial@test.com"
        assert data["phone"] == "+255700000088"

    def test_null_enrollment_fields_ignored(self, client, admin_user):
        token = _login(client, "admin@test.com", "Admin1234")
        resp = client.patch(
            f"/api/v1/users/{admin_user.id}",
            json={"email": "admin@test.com", "department_id": None, "program_id": None},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200


class TestInternalRecipients:
    def test_recipients_filter_by_email(self, client, admin_user):
        resp = client.get(
            "/api/v1/users/internal/recipients",
            query_string={"email": "admin@test.com"},
            headers={"X-Internal-Service-Key": "dev-internal-service-key"},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data) == 1
        assert data[0]["email"] == "admin@test.com"
