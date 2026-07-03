import os
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from app.config import config
from app.extensions import db, migrate, jwt, limiter, mail, cors, get_redis
from app.services.token_service import is_token_blacklisted


def create_app(config_name: str = None) -> Flask:
    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)
    mail.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    # JWT callbacks
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        return is_token_blacklisted(jwt_payload["jti"])

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({"success": False, "message": "Token has been revoked."}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"success": False, "message": "Token has expired."}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({"success": False, "message": "Invalid token."}), 422

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({"success": False, "message": "Authorization token required."}), 401

    # Blueprints
    from app.routes import auth_bp, users_bp, internal_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(internal_bp)

    # Health check
    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "auth-service"}), 200

    # Create tables and seed roles on first run
    with app.app_context():
        db.create_all()
        from app.services.auth_service import seed_roles
        seed_roles()

    return app
