from app import create_app
from app.celery_app import celery  # noqa: F401 — ensures API uses the Redis broker

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004, debug=False)
