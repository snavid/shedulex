from unittest.mock import patch

import pytest


class TestClassAnnouncement:
    @patch("app.routes.notifications.enqueue_task")
    @patch("app.services.timetable_client.get_timetable_entry")
    def test_class_announcement_queues_broadcast(self, mock_entry, mock_enqueue, client, app):
        mock_entry.return_value = {
            "id": "entry-1",
            "student_group": {"id": "group-b", "name": "Year 1 Group B"},
            "course": {"name": "CS102", "department": {"university_id": "uni-str"}},
        }
        with app.app_context():
            from flask_jwt_extended import create_access_token

            token = create_access_token(
                identity="lec-1",
                additional_claims={"role": "lecturer", "university_id": "uni-str"},
            )
            resp = client.post(
                "/api/v1/notifications/class-announcement",
                json={
                    "entry_id": "entry-1",
                    "message": "Come with your assignment",
                    "channel": "sms",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 202
        assert "Group B" in resp.get_json()["message"]
        mock_enqueue.assert_called_once()
        kwargs = mock_enqueue.call_args.kwargs
        assert kwargs["student_group_id"] == "group-b"
        assert kwargs["audience"] == "students"

    @patch("app.services.recipient_resolver.fetch_recipients")
    @patch("app.services.dispatch_service.send_sms", return_value=(True, None))
    def test_broadcast_student_group_filter(self, _mock_sms, mock_fetch, app):
        mock_fetch.return_value = [{"id": "s1", "phone": "+255700000001"}]
        with app.app_context():
            from app.tasks.reminder_tasks import broadcast_announcement

            broadcast_announcement(
                subject="CS102",
                body="Assignment due",
                audience="students",
                channel="sms",
                university_id="uni-str",
                student_group_id="group-b",
            )
        mock_fetch.assert_called()
        assert mock_fetch.call_args.kwargs.get("student_group_id") == "group-b"
