from unittest.mock import patch

import pytest


@pytest.fixture
def app():
    from app import create_app

    app = create_app("testing")
    app.config["DEFAULT_SMS_PHONE"] = "+255749300606"
    app.config["BEEM_API_KEY"] = "test-key"
    app.config["BEEM_SECRET_KEY"] = "test-secret"
    return app


class TestDeliverMessage:
    @patch("app.services.dispatch_service.send_sms", return_value=(True, None))
    def test_sms_uses_default_phone_when_missing(self, mock_send_sms, app):
        with app.app_context():
            from app.services.dispatch_service import deliver_message

            ok, err = deliver_message(
                phone=None,
                email=None,
                channel="sms",
                subject="Exam",
                body="Starts Monday",
            )

        assert ok is True
        assert err is None
        mock_send_sms.assert_called_once_with("255749300606", "Exam: Starts Monday")

    @patch("app.services.dispatch_service.send_sms", return_value=(True, None))
    def test_sms_uses_recipient_phone_when_present(self, mock_send_sms, app):
        with app.app_context():
            from app.services.dispatch_service import deliver_message

            ok, err = deliver_message(
                phone="+255712345678",
                email=None,
                channel="sms",
                subject="",
                body="Hello",
            )

        assert ok is True
        assert err is None
        mock_send_sms.assert_called_once_with("255712345678", "Hello")

    @patch("app.services.dispatch_service.send_sms", return_value=(True, None))
    def test_sms_includes_subject_prefix(self, mock_send_sms, app):
        with app.app_context():
            from app.services.dispatch_service import deliver_message

            deliver_message(
                phone="+255700000001",
                email=None,
                channel="sms",
                subject="Exam update",
                body="Postponed to Monday",
            )

        mock_send_sms.assert_called_once_with(
            "255700000001",
            "Exam update: Postponed to Monday",
        )

    @patch(
        "app.services.dispatch_service.send_sms",
        return_value=(False, "Beem: Invalid Authentication Parameters (401, code 120)"),
    )
    def test_sms_failure_surfaces_beem_error(self, mock_send_sms, app):
        with app.app_context():
            from app.services.dispatch_service import deliver_message

            ok, err = deliver_message(
                phone="+255700000001",
                email=None,
                channel="sms",
                subject="Test",
                body="Hello",
            )

        assert ok is False
        assert err == "Beem: Invalid Authentication Parameters (401, code 120)"


class TestDispatchNotification:
    @patch("app.services.dispatch_service.send_sms", return_value=(True, None))
    def test_metadata_records_default_sms_dest(self, mock_send_sms, app):
        with app.app_context():
            from app.extensions import db
            from app.models.notification import Notification
            from app.services.dispatch_service import dispatch_notification

            db.create_all()
            dispatch_notification(
                recipient_id="user-1",
                phone=None,
                email="user@test.com",
                subject="Exam",
                body="Starts Monday",
                channel="sms",
            )
            notif = Notification.query.first()

        assert notif.recipient_phone is None
        assert notif.metadata_.get("sms_dest") == "+255749300606"
        mock_send_sms.assert_called_once_with("255749300606", "Exam: Starts Monday")
