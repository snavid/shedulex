from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
from marshmallow import ValidationError

from app.extensions import limiter
from app.middleware.portal_auth import portal_jwt_required
from app.models.user import User
from app.schemas import PortalSessionSchema, PortalSubscribeSchema
from app.services import auth_service

portal_bp = Blueprint("portal", __name__, url_prefix="/api/v1/portal")

session_schema = PortalSessionSchema()
subscribe_schema = PortalSubscribeSchema()


@portal_bp.post("/session")
@limiter.limit("10 per minute")
def portal_session():
    try:
        data = session_schema.load(request.get_json() or {})
    except ValidationError as e:
        return jsonify({"success": False, "message": "Validation failed", "errors": e.messages}), 422

    try:
        tokens = auth_service.create_portal_session(
            data["university_code"],
            data["registration_number"],
            data["phone_last4"],
        )
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 401
    except RuntimeError as e:
        return jsonify({"success": False, "message": str(e)}), 500

    return jsonify({"success": True, "data": tokens}), 200


@portal_bp.post("/subscribe")
@portal_jwt_required
def portal_subscribe():
    user = User.query.get(get_jwt_identity())
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404

    try:
        data = subscribe_schema.load(request.get_json() or {})
    except ValidationError as e:
        return jsonify({"success": False, "message": "Validation failed", "errors": e.messages}), 422

    if not data.get("phone") and not data.get("email"):
        return jsonify({"success": False, "message": "Provide phone and/or email to update."}), 422

    user = auth_service.update_portal_subscription(user, data)
    return jsonify({"success": True, "data": user.to_dict()}), 200
