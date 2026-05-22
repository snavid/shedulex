import logging
import os
from flask import Flask, jsonify
from app.config import config
from app.extensions import db, migrate, jwt, cors

logger = logging.getLogger(__name__)


def create_app(config_name: str = None) -> Flask:
    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    from app.routes import timetable_bp, resources_bp
    app.register_blueprint(timetable_bp)
    app.register_blueprint(resources_bp)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "timetable-engine"}), 200

    with app.app_context():
        try:
            db.create_all()
        except Exception as exc:
            logger.warning("db.create_all() failed (non-fatal): %s", exc)
        try:
            from app.services.timetable_service import seed_default_slots
            seed_default_slots()
        except Exception as exc:
            logger.warning("seed_default_slots() failed (non-fatal): %s", exc)

    return app
