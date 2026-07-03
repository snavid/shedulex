from app.celery_app import celery

_flask_app = None


def _get_flask_app():
    global _flask_app
    if _flask_app is None:
        from app import create_app
        _flask_app = create_app()
    return _flask_app


class FlaskTask(celery.Task):
    def __call__(self, *args, **kwargs):
        with _get_flask_app().app_context():
            return self.run(*args, **kwargs)


celery.Task = FlaskTask

if __name__ == "__main__":
    celery.start()
