import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "postgresql://shedulex:shedulex_secret@localhost:5543/notification_db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-change-me")
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
    TIMETABLE_SERVICE_URL = os.environ.get("TIMETABLE_SERVICE_URL", "http://timetable-engine:5002")
    INTERNAL_SERVICE_KEY = os.environ.get("INTERNAL_SERVICE_KEY", "dev-internal-service-key")


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
