import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "postgresql://shedulex:shedulex_secret@localhost:5432/analytics_db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-change-me")
    TIMETABLE_SERVICE_URL = os.environ.get("TIMETABLE_SERVICE_URL", "http://timetable-engine:5002")


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config = {"development": DevelopmentConfig, "production": Config, "testing": TestingConfig, "default": DevelopmentConfig}
