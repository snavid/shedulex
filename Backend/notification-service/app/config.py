import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "postgresql://shedulex:shedulex_secret@localhost:5543/notification_db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-change-me")
    JWT_ENCODE_ISSUER = os.environ.get("JWT_ISSUER", "shedulex")
    JWT_DECODE_ISSUER = os.environ.get("JWT_ISSUER", "shedulex")
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6490/0")
    CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6490/0")
    CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6490/0")
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@shedulex.ac")
    BEEM_API_KEY = os.environ.get("BEEM_API_KEY", "")
    BEEM_SECRET_KEY = os.environ.get("BEEM_SECRET_KEY", "")
    BEEM_SENDER_NAME = os.environ.get("BEEM_SENDER_NAME", "SHEDULEX")
    DEFAULT_SMS_PHONE = os.environ.get("DEFAULT_SMS_PHONE", "+255749300606")
    TIMETABLE_SERVICE_URL = os.environ.get("TIMETABLE_SERVICE_URL", "http://timetable-engine:5002")
    AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://auth-service:5001")
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    INTERNAL_SERVICE_KEY = os.environ.get("INTERNAL_SERVICE_KEY", "dev-internal-service-key")
    TIMETABLE_EVENT_DEBOUNCE_SECONDS = int(os.environ.get("TIMETABLE_EVENT_DEBOUNCE_SECONDS", 300))
    TIMETABLE_NOTIFY_ENABLED = os.environ.get("TIMETABLE_NOTIFY_ENABLED", "true").lower() == "true"
    CALENDAR_SERVICE_URL = os.environ.get("CALENDAR_SERVICE_URL", "http://calendar-service:5005")


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config = {
    "development": DevelopmentConfig,
    "production": Config,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
