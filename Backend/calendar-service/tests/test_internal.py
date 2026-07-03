from datetime import datetime, timezone

import pytest


class TestInternalEventsToday:
    def test_requires_internal_key(self, client):
        resp = client.get("/api/v1/calendar/internal/events/today")
        assert resp.status_code == 403

    def test_returns_today_events(self, client, app):
        from app.extensions import db
        from app.models.event import AcademicEvent

        now = datetime.now(timezone.utc)
        with app.app_context():
            db.session.add(AcademicEvent(
                title="Today Exam",
                event_type="exam",
                start_datetime=now,
                university_id="uni-1",
            ))
            db.session.commit()

            resp = client.get(
                "/api/v1/calendar/internal/events/today",
                headers={"X-Internal-Service-Key": "test-internal-key"},
            )

        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data) >= 1
        assert data[0]["title"] == "Today Exam"
