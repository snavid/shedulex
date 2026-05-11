from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
import redis

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cors = CORS()

_redis_client = None


def get_redis():
    global _redis_client
    if _redis_client is None:
        from flask import current_app
        _redis_client = redis.from_url(current_app.config["REDIS_URL"], decode_responses=True)
    return _redis_client
