import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "postgresql://shedulex:shedulex_secret@localhost:5432/adjustment_db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-change-me")
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    TIMETABLE_SERVICE_URL = os.environ.get("TIMETABLE_SERVICE_URL", "http://timetable-engine:5002")


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
