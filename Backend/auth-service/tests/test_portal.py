from unittest.mock import patch

import pytest


@pytest.fixture
def student_user(db, app):
    from app.models.user import User, Role

    role = Role.query.filter_by(name="student").first()
    existing = User.query.filter_by(
        university_id="uni-str",
        registration_number="REG2026001",
    ).first()
    if existing:
        yield existing
        return

    user = User(
        email="student@test.com",
        username="reg2026001",
        first_name="Test",
        last_name="Student",
        phone="+255749300606",
        registration_number="REG2026001",
        university_id="uni-str",
        student_group_id="group-b",
        program_id="prog-1",
        department_id="dept-1",
        role_id=role.id,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    user.set_password("Student1234")
    db.session.add(user)
    db.session.commit()
    yield user


class TestPortalSession:
    @patch("app.services.auth_service._resolve_university_by_code")
    def test_portal_session_success(self, mock_uni, client, student_user):
        mock_uni.return_value = {"id": "uni-str", "code": "STR"}
        resp = client.post(
            "/api/v1/portal/session",
            json={
                "university_code": "STR",
                "registration_number": "REG2026001",
                "phone_last4": "0606",
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["access_token"]
        assert data["user"]["registration_number"] == "REG2026001"

    @patch("app.services.auth_service._resolve_university_by_code")
    def test_portal_session_invalid_phone(self, mock_uni, client, student_user):
        mock_uni.return_value = {"id": "uni-str", "code": "STR"}
        resp = client.post(
            "/api/v1/portal/session",
            json={
                "university_code": "STR",
                "registration_number": "REG2026001",
                "phone_last4": "9999",
            },
        )
        assert resp.status_code == 401


class TestCreateStudent:
    @patch("app.services.auth_service._resolve_department_name", return_value="Computer Science")
    def test_create_student(self, _mock_dept, client, app, admin_user):
        from flask_jwt_extended import create_access_token

        admin_user.university_id = "uni-str"
        from app.extensions import db
        db.session.commit()

        with app.app_context():
            token = create_access_token(
                identity=str(admin_user.id),
                additional_claims={"role": "admin", "university_id": "uni-str"},
            )

        resp = client.post(
            "/api/v1/users/students",
            json={
                "first_name": "Jane",
                "last_name": "Doe",
                "registration_number": "REG2026002",
                "phone": "+255700000099",
                "department_id": "dept-1",
                "program_id": "prog-1",
                "student_group_id": "group-b",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["data"]["registration_number"] == "REG2026002"

    @patch("app.services.auth_service._resolve_department_name", return_value="Computer Science")
    def test_duplicate_registration_number(self, _mock_dept, client, app, admin_user, student_user):
        from flask_jwt_extended import create_access_token
        from app.extensions import db

        admin_user.university_id = "uni-str"
        db.session.commit()

        with app.app_context():
            token = create_access_token(
                identity=str(admin_user.id),
                additional_claims={"role": "admin", "university_id": "uni-str"},
            )

        resp = client.post(
            "/api/v1/users/students",
            json={
                "first_name": "Dup",
                "last_name": "Student",
                "registration_number": "REG2026001",
                "phone": "+255700000088",
                "department_id": "dept-1",
                "program_id": "prog-1",
                "student_group_id": "group-b",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409
