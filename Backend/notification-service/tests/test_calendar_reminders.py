from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def app():
    from app import create_app
    app = create_app("testing")
    app.config["INTERNAL_SERVICE_KEY"] = "test-internal-key"
    return app


class TestCalendarReminders:
    @patch("app.tasks.reminder_tasks._notify_calendar_event")
    @patch("app.services.calendar_client.fetch_today_events")
    def test_schedule_calendar_event_reminders(self, mock_fetch, mock_notify, app):
        from app.tasks.reminder_tasks import schedule_calendar_event_reminders

        mock_fetch.return_value = [{"id": "evt-1", "title": "Exam"}]
        with app.app_context():
            schedule_calendar_event_reminders()
        mock_notify.assert_called_once()

    @patch("app.services.dispatch_service.dispatch_notification", return_value=True)
    @patch("app.services.recipient_resolver.resolve_calendar_event_recipients")
    @patch("app.services.timetable_events._redis_client")
    def test_notify_calendar_event_dedupes(self, mock_redis_factory, mock_resolve, mock_dispatch, app):
        from app.tasks.reminder_tasks import _notify_calendar_event

        mock_client = MagicMock()
        mock_client.get.return_value = None
        mock_redis_factory.return_value = mock_client
        mock_resolve.return_value = [{"id": "u1", "phone": "+255700000001", "email": "a@test.com"}]

        event = {
            "id": "evt-1",
            "title": "Exam",
            "start": "2026-07-03T09:00:00+00:00",
            "university_id": "uni-1",
        }
        with app.app_context():
            _notify_calendar_event(event)

        mock_dispatch.assert_called_once()
        mock_client.setex.assert_called_once()
