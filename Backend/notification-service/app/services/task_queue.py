from __future__ import annotations

from celery.exceptions import OperationalError
from flask import current_app
from kombu.exceptions import OperationalError as KombuOperationalError

_BROKER_ERRORS = (OperationalError, KombuOperationalError, ConnectionError, OSError)


def enqueue_task(task, *args, sync_fallback: bool = True, **kwargs):
    """Queue a Celery task; run synchronously if the broker is unreachable."""
    try:
        return task.delay(*args, **kwargs)
    except _BROKER_ERRORS as exc:
        if not sync_fallback:
            raise
        current_app.logger.warning(
            "Broker unavailable for %s, running synchronously: %s",
            task.name,
            exc,
        )
        return task.apply(args=args, kwargs=kwargs)


def enqueue_task_async(task, *, args=None, kwargs=None, sync_fallback: bool = True, **options):
    """Queue a Celery task with apply_async options; sync fallback on broker failure."""
    args = args or []
    kwargs = kwargs or {}
    try:
        return task.apply_async(args=args, kwargs=kwargs, **options)
    except _BROKER_ERRORS as exc:
        if not sync_fallback:
            raise
        current_app.logger.warning(
            "Broker unavailable for %s, running synchronously: %s",
            task.name,
            exc,
        )
        return task.apply(args=args, kwargs=kwargs)
