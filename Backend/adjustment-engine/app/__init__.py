import os
from flask import Flask, jsonify
from app.config import config
from app.extensions import db, migrate, jwt, cors


def create_app(config_name: str = None) -> Flask:
    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    from app.routes import adjustments_bp
    app.register_blueprint(adjustments_bp)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "adjustment-engine"}), 200

    with app.app_context():
        db.create_all()

    return app
