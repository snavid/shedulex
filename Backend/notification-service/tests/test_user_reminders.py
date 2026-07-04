from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


@pytest.fixture
def app():
    from app import create_app
    app = create_app("testing")
    app.config["INTERNAL_SERVICE_KEY"] = "test-internal-key"
    app.config["JWT_SECRET_KEY"] = "test-jwt-secret"
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _token(app, user_id="user-1", role="student", portal=False):
    from flask_jwt_extended import create_access_token
    with app.app_context():
        claims = {"role": role, "email": "student@test.com", "university_id": "uni-1"}
        if portal:
            claims["portal"] = True
        return create_access_token(identity=user_id, additional_claims=claims)


def _future_event_start(hours=48):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _reminder_payload(**overrides):
    payload = {
        "event_source": "session",
        "event_key": "session:entry-1:2026-07-06",
        "event_title": "cs30323 · KU-CLAB1",
        "event_start": _future_event_start(),
        "event_end": _future_event_start(hours=49),
        "channel": "sms",
        "lead_times": [1440, 60, 15],
        "metadata": {"course_code": "cs30323", "room": "KU-CLAB1"},
    }
    payload.update(overrides)
    return payload


class TestUserReminders:
    @patch("app.tasks.reminder_tasks.send_lecture_reminder")
    @patch("app.services.reminder_service.fetch_user_by_id")
    def test_creates_multiple_lead_times(self, mock_fetch, mock_task, client, app):
        mock_fetch.return_value = {
            "email": "student@test.com",
            "phone": "+255700000001",
            "first_name": "Jane",
            "last_name": "Doe",
        }
        mock_task.delay = lambda *a, **k: None
        mock_task.apply_async = lambda *a, **k: None

        with app.app_context():
            resp = client.post(
                "/api/v1/notifications/reminders",
                json=_reminder_payload(),
                headers={"Authorization": f"Bearer {_token(app)}"},
            )

        assert resp.status_code == 201
        data = resp.get_json()
        assert len(data["data"]) == 3
        assert "3 reminder(s) scheduled" in data["message"]

    @patch("app.services.reminder_service.fetch_user_by_id")
    def test_rejects_sms_without_phone(self, mock_fetch, client, app):
        mock_fetch.return_value = {"email": "student@test.com", "phone": None}

        with app.app_context():
            resp = client.post(
                "/api/v1/notifications/reminders",
                json=_reminder_payload(),
                headers={"Authorization": f"Bearer {_token(app)}"},
            )

        assert resp.status_code == 422
        assert "phone number" in resp.get_json()["message"].lower()

    @patch("app.services.reminder_service.fetch_user_by_id")
    def test_rejects_past_event(self, mock_fetch, client, app):
        mock_fetch.return_value = {
            "email": "student@test.com",
            "phone": "+255700000001",
        }
        past_start = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        with app.app_context():
            resp = client.post(
                "/api/v1/notifications/reminders",
                json=_reminder_payload(event_start=past_start, lead_times=[60, 15, 0]),
                headers={"Authorization": f"Bearer {_token(app)}"},
            )

        assert resp.status_code == 422
        assert "past" in resp.get_json()["message"].lower()

    @patch("app.tasks.reminder_tasks.send_lecture_reminder")
    @patch("app.services.reminder_service.fetch_user_by_id")
    def test_prevents_duplicate_lead_time(self, mock_fetch, mock_task, client, app):
        mock_fetch.return_value = {
            "email": "student@test.com",
            "phone": "+255700000001",
        }
        mock_task.delay = lambda *a, **k: None
        mock_task.apply_async = lambda *a, **k: None

        with app.app_context():
            headers = {"Authorization": f"Bearer {_token(app)}"}
            payload = _reminder_payload(lead_times=[60])
            resp1 = client.post("/api/v1/notifications/reminders", json=payload, headers=headers)
            assert resp1.status_code == 201

            resp2 = client.post("/api/v1/notifications/reminders", json=payload, headers=headers)
            assert resp2.status_code == 422

    @patch("app.tasks.reminder_tasks.send_lecture_reminder")
    @patch("app.services.reminder_service.fetch_user_by_id")
    def test_cancel_own_reminder(self, mock_fetch, mock_task, client, app):
        mock_fetch.return_value = {
            "email": "student@test.com",
            "phone": "+255700000001",
        }
        mock_task.delay = lambda *a, **k: None
        mock_task.apply_async = lambda *a, **k: None

        with app.app_context():
            headers = {"Authorization": f"Bearer {_token(app)}"}
            create_resp = client.post(
                "/api/v1/notifications/reminders",
                json=_reminder_payload(lead_times=[60]),
                headers=headers,
            )
            reminder_id = create_resp.get_json()["data"][0]["id"]

            cancel_resp = client.delete(
                f"/api/v1/notifications/reminders/{reminder_id}",
                headers=headers,
            )
            assert cancel_resp.status_code == 200
            assert cancel_resp.get_json()["data"]["status"] == "cancelled"

    @patch("app.tasks.reminder_tasks.send_lecture_reminder")
    @patch("app.services.reminder_service.fetch_user_by_id")
    def test_cannot_cancel_others_reminder(self, mock_fetch, mock_task, client, app):
        mock_fetch.return_value = {
            "email": "student@test.com",
            "phone": "+255700000001",
        }
        mock_task.delay = lambda *a, **k: None
        mock_task.apply_async = lambda *a, **k: None

        with app.app_context():
            create_resp = client.post(
                "/api/v1/notifications/reminders",
                json=_reminder_payload(lead_times=[60]),
                headers={"Authorization": f"Bearer {_token(app, user_id='user-1')}"},
            )
            reminder_id = create_resp.get_json()["data"][0]["id"]

            cancel_resp = client.delete(
                f"/api/v1/notifications/reminders/{reminder_id}",
                headers={"Authorization": f"Bearer {_token(app, user_id='user-2')}"},
            )
            assert cancel_resp.status_code == 404

    @patch("app.tasks.reminder_tasks.send_lecture_reminder")
    @patch("app.services.reminder_service.fetch_user_by_id")
    def test_lecturer_can_create_reminder(self, mock_fetch, mock_task, client, app):
        mock_fetch.return_value = {
            "email": "lecturer@test.com",
            "phone": "+255700000002",
        }
        mock_task.delay = lambda *a, **k: None
        mock_task.apply_async = lambda *a, **k: None

        with app.app_context():
            resp = client.post(
                "/api/v1/notifications/reminders",
                json=_reminder_payload(),
                headers={"Authorization": f"Bearer {_token(app, role='lecturer')}"},
            )
        assert resp.status_code == 201

    @patch("app.tasks.reminder_tasks.send_lecture_reminder")
    @patch("app.services.reminder_service.fetch_user_by_id")
    def test_portal_student_can_create_session_reminder(self, mock_fetch, mock_task, client, app):
        mock_fetch.return_value = {
            "email": "student@test.com",
            "phone": "+255700000001",
        }
        mock_task.delay = lambda *a, **k: None
        mock_task.apply_async = lambda *a, **k: None

        with app.app_context():
            resp = client.post(
                "/api/v1/notifications/reminders",
                json=_reminder_payload(lead_times=[60]),
                headers={"Authorization": f"Bearer {_token(app, portal=True)}"},
            )
        assert resp.status_code == 201

    @patch("app.services.reminder_service.fetch_user_by_id")
    def test_portal_token_rejects_calendar_source(self, mock_fetch, client, app):
        mock_fetch.return_value = {
            "email": "student@test.com",
            "phone": "+255700000001",
        }

        with app.app_context():
            resp = client.post(
                "/api/v1/notifications/reminders",
                json=_reminder_payload(
                    event_source="calendar",
                    event_key="calendar:evt-1",
                ),
                headers={"Authorization": f"Bearer {_token(app, portal=True)}"},
            )
        assert resp.status_code == 403

    @patch("app.tasks.reminder_tasks.send_lecture_reminder")
    @patch("app.services.reminder_service.fetch_user_by_id")
    def test_portal_student_can_list_and_cancel(self, mock_fetch, mock_task, client, app):
        mock_fetch.return_value = {
            "email": "student@test.com",
            "phone": "+255700000001",
        }
        mock_task.delay = lambda *a, **k: None
        mock_task.apply_async = lambda *a, **k: None

        with app.app_context():
            headers = {"Authorization": f"Bearer {_token(app, portal=True)}"}
            create_resp = client.post(
                "/api/v1/notifications/reminders",
                json=_reminder_payload(lead_times=[60]),
                headers=headers,
            )
            assert create_resp.status_code == 201
            reminder_id = create_resp.get_json()["data"][0]["id"]

            list_resp = client.get("/api/v1/notifications/reminders", headers=headers)
            assert list_resp.status_code == 200
            assert len(list_resp.get_json()["data"]) >= 1

            cancel_resp = client.delete(
                f"/api/v1/notifications/reminders/{reminder_id}",
                headers=headers,
            )
            assert cancel_resp.status_code == 200

    @patch("app.tasks.reminder_tasks.send_lecture_reminder")
    @patch("app.services.reminder_service.fetch_user_by_id")
    def test_weekly_recurrence_creates_multiple_occurrences(self, mock_fetch, mock_task, client, app):
        mock_fetch.return_value = {
            "email": "student@test.com",
            "phone": "+255700000001",
        }
        mock_task.delay = lambda *a, **k: None
        mock_task.apply_async = lambda *a, **k: None

        first_start = datetime.now(timezone.utc) + timedelta(days=7)
        repeat_until = (first_start + timedelta(days=21)).date().isoformat()

        with app.app_context():
            resp = client.post(
                "/api/v1/notifications/reminders",
                json=_reminder_payload(
                    event_start=first_start.isoformat(),
                    lead_times=[60],
                    repeat_weekly_until=repeat_until,
                    metadata={"entry_id": "entry-1", "course_code": "cs30323"},
                ),
                headers={"Authorization": f"Bearer {_token(app)}"},
            )

        assert resp.status_code == 201
        data = resp.get_json()
        assert len(data["data"]) == 4
        keys = {r["event_key"] for r in data["data"]}
        assert len(keys) == 4
        assert all(k.startswith("session:entry-1:") for k in keys)

    @patch("app.tasks.reminder_tasks.send_lecture_reminder")
    @patch("app.services.reminder_service.fetch_user_by_id")
    def test_weekly_recurrence_skips_duplicates(self, mock_fetch, mock_task, client, app):
        mock_fetch.return_value = {
            "email": "student@test.com",
            "phone": "+255700000001",
        }
        mock_task.delay = lambda *a, **k: None
        mock_task.apply_async = lambda *a, **k: None

        first_start = datetime.now(timezone.utc) + timedelta(days=7)
        repeat_until = (first_start + timedelta(days=14)).date().isoformat()
        payload = _reminder_payload(
            event_start=first_start.isoformat(),
            lead_times=[60],
            repeat_weekly_until=repeat_until,
            metadata={"entry_id": "entry-1"},
        )

        with app.app_context():
            headers = {"Authorization": f"Bearer {_token(app)}"}
            resp1 = client.post("/api/v1/notifications/reminders", json=payload, headers=headers)
            assert resp1.status_code == 201
            assert len(resp1.get_json()["data"]) == 3

            resp2 = client.post("/api/v1/notifications/reminders", json=payload, headers=headers)
            assert resp2.status_code == 422

    def test_portal_token_rejected_for_non_student(self, client, app):
        with app.app_context():
            resp = client.post(
                "/api/v1/notifications/reminders",
                json=_reminder_payload(),
                headers={"Authorization": f"Bearer {_token(app, role='admin', portal=True)}"},
            )
        assert resp.status_code == 403

    @patch("app.tasks.reminder_tasks.send_lecture_reminder")
    @patch("app.services.reminder_service.fetch_user_by_id")
    def test_list_reminders_by_event_key(self, mock_fetch, mock_task, client, app):
        mock_fetch.return_value = {
            "email": "student@test.com",
            "phone": "+255700000001",
        }
        mock_task.delay = lambda *a, **k: None
        mock_task.apply_async = lambda *a, **k: None

        with app.app_context():
            headers = {"Authorization": f"Bearer {_token(app)}"}
            client.post(
                "/api/v1/notifications/reminders",
                json=_reminder_payload(lead_times=[60, 15]),
                headers=headers,
            )
            list_resp = client.get(
                "/api/v1/notifications/reminders?event_key=session:entry-1:2026-07-06",
                headers=headers,
            )
        assert list_resp.status_code == 200
        assert len(list_resp.get_json()["data"]) == 2
