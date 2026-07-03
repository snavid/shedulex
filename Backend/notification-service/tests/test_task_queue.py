from unittest.mock import MagicMock

import pytest
from celery.exceptions import OperationalError

from app.services.task_queue import enqueue_task, enqueue_task_async


class TestTaskQueue:
    def test_enqueue_task_sync_fallback(self, app):
        mock_task = MagicMock()
        mock_task.name = "tasks.test"
        mock_task.delay.side_effect = OperationalError("connection refused")
        with app.app_context():
            enqueue_task(mock_task, "arg1", kw="val")
        mock_task.apply.assert_called_once_with(args=("arg1",), kwargs={"kw": "val"})

    def test_enqueue_task_async_sync_fallback(self, app):
        mock_task = MagicMock()
        mock_task.name = "tasks.test_async"
        mock_task.apply_async.side_effect = OperationalError("connection refused")
        with app.app_context():
            enqueue_task_async(mock_task, args=["id-1"], countdown=300)
        mock_task.apply.assert_called_once_with(args=["id-1"], kwargs={})

    def test_enqueue_task_reraises_when_fallback_disabled(self, app):
        mock_task = MagicMock()
        mock_task.delay.side_effect = OperationalError("connection refused")
        with app.app_context():
            with pytest.raises(OperationalError):
                enqueue_task(mock_task, "arg1", sync_fallback=False)
