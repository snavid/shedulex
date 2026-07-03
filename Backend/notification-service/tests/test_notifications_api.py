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


class TestSendNotification:
    def test_accepts_field_aliases(self, client, app):
        with app.app_context():
            with patch("app.routes.notifications.deliver_message", return_value=(True, None)):
                resp = client.post(
                    "/api/v1/notifications/send",
                    json={
                        "recipient_email": "user@test.com",
                        "recipient_phone": "+255700000001",
                        "notification_type": "reminder",
                        "channel": "both",
                        "subject": "Test",
                        "body": "Hello",
                    },
                    headers=_auth_headers(app),
                )
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        assert data["notification_type"] == "reminder"
        assert data["recipient_email"] == "user@test.com"

    def test_both_channel_partial_success(self, client, app):
        with app.app_context():
            with patch(
                "app.routes.notifications.deliver_message",
                return_value=(True, "Email delivery failed"),
            ):
                resp = client.post(
                    "/api/v1/notifications/send",
                    json={
                        "email": "user@test.com",
                        "phone": "+255700000001",
                        "channel": "both",
                        "subject": "Test",
                        "body": "Hello",
                    },
                    headers=_auth_headers(app),
                )
        assert resp.status_code == 201
        assert resp.get_json()["data"]["status"] == "sent"

    def test_sms_requires_phone(self, client, app):
        with app.app_context():
            resp = client.post(
                "/api/v1/notifications/send",
                json={
                    "email": "user@test.com",
                    "channel": "sms",
                    "subject": "Test",
                    "body": "Hello",
                },
                headers=_auth_headers(app),
            )
        assert resp.status_code == 422


class TestBroadcast:
    @patch("app.tasks.reminder_tasks.broadcast_announcement")
    def test_broadcast_audience_payload(self, mock_task, client, app):
        with app.app_context():
            resp = client.post(
                "/api/v1/notifications/broadcast",
                json={
                    "subject": "Announcement",
                    "body": "Hello everyone",
                    "audience": "students",
                    "channel": "sms",
                    "department_id": "dept-1",
                },
                headers=_auth_headers(app),
            )
        assert resp.status_code == 202
        mock_task.delay.assert_called_once()
        kwargs = mock_task.delay.call_args.kwargs
        assert kwargs["audience"] == "students"
        assert kwargs["channel"] == "sms"

    @patch("app.tasks.reminder_tasks.broadcast_announcement")
    def test_broadcast_falls_back_when_broker_unavailable(self, mock_task, client, app):
        from celery.exceptions import OperationalError

        mock_task.delay.side_effect = OperationalError("connection refused")
        with app.app_context():
            resp = client.post(
                "/api/v1/notifications/broadcast",
                json={
                    "subject": "Announcement",
                    "body": "Hello everyone",
                    "audience": "all",
                    "channel": "sms",
                },
                headers=_auth_headers(app),
            )
        assert resp.status_code == 202
        mock_task.apply.assert_called_once()

    def test_broadcast_requires_university_id(self, client, app):
        with app.app_context():
            from flask_jwt_extended import create_access_token

            token = create_access_token(
                identity="admin-1",
                additional_claims={"role": "admin"},
            )
            resp = client.post(
                "/api/v1/notifications/broadcast",
                json={
                    "subject": "Announcement",
                    "body": "Hello everyone",
                    "audience": "all",
                    "channel": "sms",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 422
        assert "University scope" in resp.get_json()["message"]

    @patch("app.services.recipient_resolver.fetch_recipients")
    @patch("app.services.dispatch_service.send_sms", return_value=(True, None))
    def test_broadcast_scoped_to_university(self, mock_send_sms, mock_fetch, app):
        mock_fetch.return_value = [
            {"id": "u1", "email": "a@str.ac", "phone": "+255700000001"},
        ]
        with app.app_context():
            from app.tasks.reminder_tasks import broadcast_announcement

            broadcast_announcement(
                subject="Exam",
                body="Starts Monday",
                audience="all",
                channel="sms",
                university_id="STR",
            )

        mock_fetch.assert_called()
        call_filters = mock_fetch.call_args_list[0].kwargs
        assert call_filters.get("university_id") == "STR"
        mock_send_sms.assert_called_once_with("255700000001", "Exam: Starts Monday")


def _auth_headers(app):
    from flask_jwt_extended import create_access_token
    with app.app_context():
        token = create_access_token(
            identity="admin-1",
            additional_claims={"role": "admin", "university_id": "uni-1"},
        )
    return {"Authorization": f"Bearer {token}"}
