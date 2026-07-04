"""Tests for Sora session cancellation (Redis flag + API + job cooperation)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestRedisCancelFlag:
    def test_cancel_flag_round_trip(self):
        from app.services import redis_pubsub

        store = {}

        mock_redis = MagicMock()
        mock_redis.set.side_effect = lambda key, val, ex=None: store.update({key: val})
        mock_redis.delete.side_effect = lambda key: store.pop(key, None)
        mock_redis.exists.side_effect = lambda key: 1 if key in store else 0

        with patch.object(redis_pubsub, "get_redis", return_value=mock_redis):
            sid = "test-session-123"
            assert redis_pubsub.is_cancelled(sid) is False

            redis_pubsub.request_cancel(sid)
            assert redis_pubsub.is_cancelled(sid) is True

            redis_pubsub.clear_cancel(sid)
            assert redis_pubsub.is_cancelled(sid) is False


class TestCancelEndpoint:
    def test_cancel_returns_202_and_sets_flag(self, app, client, db):
        from flask_jwt_extended import create_access_token
        from app.models.adjustment import ConversationSession
        from app.services import redis_pubsub

        store = {}
        mock_redis = MagicMock()
        mock_redis.set.side_effect = lambda key, val, ex=None: store.update({key: val})
        mock_redis.exists.side_effect = lambda key: 1 if key in store else 0

        with app.app_context():
            session = ConversationSession(
                timetable_id="tt-1",
                user_id="user-1",
                user_name="Test User",
                messages=[],
                status="processing",
            )
            db.session.add(session)
            db.session.commit()
            session_id = session.id

            token = create_access_token(identity="user-1")
            headers = {"Authorization": f"Bearer {token}"}

            with patch.object(redis_pubsub, "get_redis", return_value=mock_redis):
                resp = client.post(f"/api/v1/adjustments/sessions/{session_id}/cancel", headers=headers)

            assert resp.status_code == 202
            assert resp.get_json()["success"] is True
            cancel_key = f"session:{session_id}:cancelled"
            assert cancel_key in store


class TestRunSessionJobCancel:
    def test_job_exits_early_when_cancelled_before_stream(self, app, db):
        from app.models.adjustment import ConversationSession
        from app.routes import adjustments
        from app.services import redis_pubsub

        published = []

        with app.app_context():
            session = ConversationSession(
                timetable_id="tt-2",
                user_id="user-2",
                user_name="Test User",
                messages=[],
                status="processing",
            )
            db.session.add(session)
            db.session.commit()
            session_id = session.id

            mock_graph = MagicMock()

            with patch.object(adjustments, "is_cancelled", return_value=True), \
                 patch.object(adjustments, "clear_cancel"), \
                 patch.object(adjustments, "publish", side_effect=lambda sid, ev: published.append(ev)), \
                 patch.object(adjustments, "get_graph", return_value=mock_graph), \
                 patch.object(adjustments.timetable_snapshots, "create_timetable_snapshot"):
                adjustments._run_session_job(app, session_id, "test prompt")

            mock_graph.stream.assert_not_called()
            assert any(ev.get("type") == "cancelled" for ev in published)
            db.session.refresh(session)
            assert session.status == "active"

    def test_job_stops_mid_stream_when_cancelled(self, app, db):
        from app.models.adjustment import ConversationSession
        from app.routes import adjustments
        from app.services import redis_pubsub

        published = []
        cancel_after = {"count": 0}

        def is_cancelled_side_effect(_sid):
            cancel_after["count"] += 1
            return cancel_after["count"] > 1

        def fake_stream(*_args, **_kwargs):
            yield {"agent": {"messages": []}}
            yield {"tools": {"messages": []}}

        mock_graph = MagicMock()
        mock_graph.stream.side_effect = fake_stream

        with app.app_context():
            session = ConversationSession(
                timetable_id="tt-3",
                user_id="user-3",
                user_name="Test User",
                messages=[],
                status="processing",
            )
            db.session.add(session)
            db.session.commit()
            session_id = session.id

            with patch.object(adjustments, "is_cancelled", side_effect=is_cancelled_side_effect), \
                 patch.object(adjustments, "clear_cancel"), \
                 patch.object(adjustments, "publish", side_effect=lambda sid, ev: published.append(ev)), \
                 patch.object(adjustments, "get_graph", return_value=mock_graph), \
                 patch.object(adjustments.timetable_snapshots, "create_timetable_snapshot"):
                adjustments._run_session_job(app, session_id, "test prompt")

            assert any(ev.get("type") == "cancelled" for ev in published)
            assert not any(ev.get("type") == "done" for ev in published)
            db.session.refresh(session)
            assert session.status == "active"


class TestSessionChatGuard:
    def test_chat_rejected_while_processing(self, app, client, db):
        from flask_jwt_extended import create_access_token
        from app.models.adjustment import ConversationSession

        with app.app_context():
            session = ConversationSession(
                timetable_id="tt-4",
                user_id="user-4",
                user_name="Test User",
                messages=[],
                status="processing",
            )
            db.session.add(session)
            db.session.commit()
            session_id = session.id

            token = create_access_token(identity="user-4")
            headers = {"Authorization": f"Bearer {token}"}

            resp = client.post(
                f"/api/v1/adjustments/sessions/{session_id}/chat",
                json={"prompt": "hello"},
                headers=headers,
            )

            assert resp.status_code == 409
            assert "processing" in resp.get_json()["message"].lower()
