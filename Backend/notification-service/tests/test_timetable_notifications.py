import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def app():
    from app import create_app
    app = create_app("testing")
    app.config["TIMETABLE_NOTIFY_ENABLED"] = True
    app.config["TIMETABLE_EVENT_DEBOUNCE_SECONDS"] = 60
    app.config["INTERNAL_SERVICE_KEY"] = "test-internal-key"
    app.config["FRONTEND_URL"] = "http://localhost:5173"
    return app


@pytest.fixture
def client(app):
    return app.test_client()


class TestMessageBuilder:
    def test_student_generation_message(self, app):
        from app.services.message_builder import build_student_message

        with app.app_context():
            subject, body = build_student_message(
                timetable_id="tt-1",
                semester=1,
                entries=[
                    {
                        "course": {"code": "CS101", "program_id": "prog-1"},
                        "time_slot": {"day": "Monday", "start_time": "08:00"},
                        "room": {"name": "A1"},
                        "student_group": {"id": "grp-a"},
                    }
                ],
                changes=[],
                program_id="prog-1",
                student_group_id="grp-a",
                is_generation=True,
            )

        assert subject == "Timetable Ready — Sem 1"
        assert "CS101" in body
        assert "/timetable/tt-1" in body

    def test_student_change_message_scoped_to_group(self, app):
        from app.services.message_builder import build_student_message

        with app.app_context():
            subject, body = build_student_message(
                timetable_id="tt-1",
                semester=1,
                entries=[],
                changes=[
                    {
                        "course_code": "CS101",
                        "student_group_id": "grp-a",
                        "old_slot": {"day": "Monday", "start_time": "08:00"},
                        "new_slot": {"day": "Tuesday", "start_time": "10:00", "room": "B2"},
                    },
                    {
                        "course_code": "CS102",
                        "student_group_id": "grp-b",
                        "old_slot": {"day": "Wednesday", "start_time": "09:00"},
                        "new_slot": {"day": "Thursday", "start_time": "11:00"},
                    },
                ],
                program_id="prog-1",
                student_group_id="grp-a",
                is_generation=False,
            )

        assert "CS101" in body
        assert "CS102" not in body

    def test_timetable_officer_message_includes_triggered_by(self, app):
        from app.services.message_builder import build_timetable_officer_message

        with app.app_context():
            subject, body = build_timetable_officer_message(
                timetable_id="tt-1",
                timetable_name="CS Sem 1",
                department_name="Computer Science",
                changes=[
                    {
                        "course_code": "CS101",
                        "old_slot": {"day": "Monday", "start_time": "08:00"},
                        "new_slot": {"day": "Tuesday", "start_time": "10:00"},
                    }
                ],
                triggered_by="officer@str.shedulex.ac",
                entry_count=10,
                is_generation=False,
            )

        assert "Timetable Updated" in subject
        assert "CS101" in body
        assert "officer@str.shedulex.ac" in body


class TestRecipientResolver:
    @patch("app.services.recipient_resolver.fetch_recipients")
    def test_hod_fallback_without_department_id(self, mock_fetch, app):
        from app.services.recipient_resolver import resolve_hod_recipients

        mock_fetch.side_effect = [
            [],
            [{"id": "hod-1", "email": "hod@str.shedulex.ac", "phone": "+255700000003", "department_id": None}],
        ]

        with app.app_context():
            hods = resolve_hod_recipients("dept-1", "uni-1")

        assert len(hods) == 1
        assert hods[0]["id"] == "hod-1"
        assert mock_fetch.call_count == 2

    @patch("app.services.recipient_resolver.fetch_recipients")
    def test_timetable_officer_included(self, mock_fetch, app):
        from app.services.recipient_resolver import resolve_timetable_officer_recipients

        mock_fetch.return_value = [
            {"id": "off-1", "email": "officer@str.shedulex.ac", "phone": "+255700000002"},
        ]

        with app.app_context():
            officers = resolve_timetable_officer_recipients("uni-1", "dept-1")

        assert len(officers) == 1
        mock_fetch.assert_called_once_with(role="timetable_officer", university_id="uni-1")

    @patch("app.services.recipient_resolver.fetch_user_by_email")
    @patch("app.services.recipient_resolver.fetch_user_by_id")
    def test_lecturer_from_change_payload(self, mock_by_id, mock_by_email, app):
        from app.services.recipient_resolver import resolve_lecturer_contacts_from_changes

        mock_by_id.return_value = None
        mock_by_email.return_value = None

        with app.app_context():
            contacts = resolve_lecturer_contacts_from_changes(
                changes=[
                    {
                        "lecturer_id": "lec-1",
                        "lecturer_email": "j.smith@str.ac",
                        "lecturer_phone": "+255700000800",
                        "lecturer_name": "Dr. Jane Smith",
                    }
                ],
                entries=[],
                lecturer_ids={"lec-1"},
            )

        assert "lec-1" in contacts
        assert contacts["lec-1"]["email"] == "j.smith@str.ac"
        assert contacts["lec-1"]["phone"] == "+255700000800"


class TestTimetableEventRoute:
    def test_internal_route_requires_key(self, client):
        resp = client.post(
            "/api/v1/notifications/internal/timetable-event",
            json={"timetable_id": "tt-1", "event_type": "entry_moved"},
        )
        assert resp.status_code == 403

    @patch("app.tasks.reminder_tasks.process_timetable_digest")
    @patch("app.routes.notifications.append_event")
    def test_buffers_mutation_event(self, mock_append, mock_task, client):
        mock_append.return_value = True
        resp = client.post(
            "/api/v1/notifications/internal/timetable-event",
            json={"timetable_id": "tt-1", "event_type": "entry_moved", "changes": []},
            headers={"X-Internal-Service-Key": "test-internal-key"},
        )
        assert resp.status_code == 202
        mock_append.assert_called_once()
        mock_task.apply_async.assert_called_once_with(args=["tt-1"], kwargs={}, countdown=60)

    @patch("app.tasks.reminder_tasks.process_timetable_digest")
    @patch("app.routes.notifications.append_event")
    def test_generation_event_dispatches_immediately(self, mock_append, mock_task, client):
        resp = client.post(
            "/api/v1/notifications/internal/timetable-event",
            json={"timetable_id": "tt-1", "event_type": "generated", "changes": []},
            headers={"X-Internal-Service-Key": "test-internal-key"},
        )
        assert resp.status_code == 202
        mock_task.delay.assert_called_once_with("tt-1")


class TestTimetableEventBuffer:
    def test_append_and_pop_events(self, app):
        from app.services.timetable_events import append_event, pop_events

        with app.app_context():
            with patch("app.services.timetable_events._redis_client") as mock_redis_factory:
                mock_client = MagicMock()
                mock_redis_factory.return_value = mock_client
                mock_client.set.return_value = True

                started = append_event("tt-1", {"event_type": "entry_moved"})
                assert started is True
                mock_client.rpush.assert_called_once()

                mock_client.lrange.return_value = [json.dumps({"event_type": "entry_moved"})]
                events = pop_events("tt-1")

        assert len(events) == 1
        assert events[0]["event_type"] == "entry_moved"


class TestProcessDigest:
    @patch("app.services.dispatch_service.dispatch_notification")
    @patch("app.services.recipient_resolver.resolve_all_recipients")
    @patch("app.services.timetable_client.get_timetable")
    @patch("app.services.timetable_events.pop_events")
    def test_process_generation_digest(
        self, mock_pop, mock_get_tt, mock_resolve, mock_dispatch, app
    ):
        from app.tasks.reminder_tasks import process_timetable_digest

        mock_pop.return_value = [{"event_type": "generated", "changes": []}]
        mock_get_tt.return_value = {
            "id": "tt-1",
            "semester": 1,
            "department_id": "dept-1",
            "department": {"id": "dept-1", "name": "Computer Science", "university_id": "uni-1"},
            "entries": [
                {
                    "lecturer": {"id": "lec-1", "phone": "+255700000001"},
                    "course": {"code": "CS101", "program_id": "prog-1"},
                    "time_slot": {"day": "Monday", "start_time": "08:00"},
                    "room": {"name": "A1"},
                }
            ],
        }
        mock_resolve.return_value = [
            {"id": "stu-1", "role": "student", "phone": "+255700000002", "program_id": "prog-1"},
            {"id": "lec-1", "role": "lecturer", "lecturer_id": "lec-1", "phone": "+255700000001"},
            {"id": "hod-1", "role": "hod", "phone": "+255700000003"},
        ]

        with app.app_context():
            process_timetable_digest("tt-1")

        assert mock_dispatch.call_count == 3

    @patch("app.services.dispatch_service.dispatch_notification")
    @patch("app.services.recipient_resolver.resolve_all_recipients")
    @patch("app.services.timetable_client.get_timetable")
    @patch("app.services.timetable_events.pop_events")
    def test_digest_notifies_hod_officer_lecturer_on_move(
        self, mock_pop, mock_get_tt, mock_resolve, mock_dispatch, app
    ):
        from app.tasks.reminder_tasks import process_timetable_digest

        change = {
            "lecturer_id": "lec-1",
            "course_code": "CS101",
            "old_slot": {"day": "Monday", "start_time": "08:00"},
            "new_slot": {"day": "Tuesday", "start_time": "10:00", "room": "B2"},
        }
        mock_pop.return_value = [
            {"event_type": "entry_moved", "triggered_by": "officer@str.shedulex.ac", "changes": [change]},
        ]
        mock_get_tt.return_value = {
            "id": "tt-1",
            "name": "CS Sem 1",
            "semester": 1,
            "department_id": "dept-1",
            "department": {"id": "dept-1", "name": "Computer Science", "university_id": "uni-1"},
            "entries": [],
        }
        mock_resolve.return_value = [
            {"id": "lec-1", "role": "lecturer", "lecturer_id": "lec-1", "phone": "+255700000001", "email": "j.smith@str.ac"},
            {"id": "hod-1", "role": "hod", "phone": "+255700000003", "email": "hod@str.shedulex.ac"},
            {"id": "off-1", "role": "timetable_officer", "phone": "+255700000002", "email": "officer@str.shedulex.ac"},
        ]

        with app.app_context():
            process_timetable_digest("tt-1")

        assert mock_dispatch.call_count == 3
        roles = {call.kwargs["metadata"]["role"] for call in mock_dispatch.call_args_list}
        assert roles == {"lecturer", "hod", "timetable_officer"}
        mock_resolve.assert_called_once()
        assert mock_resolve.call_args.kwargs["changes"] == [change]

    @patch("app.services.dispatch_service.dispatch_notification")
    @patch("app.services.recipient_resolver.resolve_lecturer_contacts_from_changes")
    @patch("app.services.recipient_resolver.fetch_recipients")
    @patch("app.services.timetable_client.get_timetable")
    @patch("app.services.timetable_events.pop_events")
    def test_swap_notifies_both_lecturers(
        self, mock_pop, mock_get_tt, mock_fetch, mock_lect_contacts, mock_dispatch, app
    ):
        from app.tasks.reminder_tasks import process_timetable_digest

        changes = [
            {"lecturer_id": "lec-1", "course_code": "CS101", "old_slot": {}, "new_slot": {}},
            {"lecturer_id": "lec-2", "course_code": "CS102", "old_slot": {}, "new_slot": {}},
        ]
        mock_pop.return_value = [{"event_type": "entry_swapped", "changes": changes}]
        mock_get_tt.return_value = {
            "id": "tt-1",
            "semester": 1,
            "department_id": "dept-1",
            "department": {"id": "dept-1", "name": "CS", "university_id": "uni-1"},
            "entries": [],
        }
        mock_fetch.return_value = []
        mock_lect_contacts.return_value = {
            "lec-1": {"id": "lec-1", "lecturer_id": "lec-1", "phone": "+1", "email": "a@x.com", "role": "lecturer"},
            "lec-2": {"id": "lec-2", "lecturer_id": "lec-2", "phone": "+2", "email": "b@x.com", "role": "lecturer"},
        }

        with app.app_context():
            process_timetable_digest("tt-1")

        lecturer_calls = [
            c for c in mock_dispatch.call_args_list
            if c.kwargs.get("metadata", {}).get("role") == "lecturer"
        ]
        assert len(lecturer_calls) == 2
