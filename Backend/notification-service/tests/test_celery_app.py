from app.celery_app import REDIS_URL, celery


def test_celery_app_broker_matches_redis_url():
    assert celery.conf.broker_url == REDIS_URL
    assert celery.main == "notification-service"
    assert "app.tasks.reminder_tasks" in celery.conf.include
