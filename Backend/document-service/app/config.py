import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "postgresql://shedulex:shedulex_secret@localhost:5543/document_db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-change-me")
    TIMETABLE_SERVICE_URL = os.environ.get("TIMETABLE_SERVICE_URL", "http://timetable-engine:5002")
    INTERNAL_SERVICE_KEY = os.environ.get("INTERNAL_SERVICE_KEY", "dev-internal-service-key")
    DOCUMENT_SHARE_SECRET = os.environ.get("DOCUMENT_SHARE_SECRET", JWT_SECRET_KEY)
    DOCUMENT_SHARE_SALT = os.environ.get("DOCUMENT_SHARE_SALT", "shedulex-document-share")
    DOCUMENT_PUBLIC_BASE_URL = os.environ.get("DOCUMENT_PUBLIC_BASE_URL", "")
    EXPORT_CACHE_TTL_SECONDS = int(os.environ.get("EXPORT_CACHE_TTL_SECONDS", 300))
    EXPORT_SHARE_TOKEN_MAX_HOURS = int(os.environ.get("EXPORT_SHARE_TOKEN_MAX_HOURS", 168))


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config = {"development": DevelopmentConfig, "production": Config, "testing": TestingConfig, "default": DevelopmentConfig}
