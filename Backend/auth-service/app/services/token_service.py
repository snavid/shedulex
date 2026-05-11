from flask_jwt_extended import create_access_token, create_refresh_token, decode_token
from app.extensions import get_redis
import uuid


TOKEN_BLACKLIST_PREFIX = "blacklist:jti:"
SESSION_PREFIX = "session:user:"


def generate_tokens(user_id: str, additional_claims: dict = None) -> dict:
    jti = str(uuid.uuid4())
    claims = {"user_id": user_id, **(additional_claims or {})}
    access_token = create_access_token(identity=user_id, additional_claims=claims)
    refresh_token = create_refresh_token(identity=user_id, additional_claims={"jti_ref": jti})
    return {"access_token": access_token, "refresh_token": refresh_token}


def blacklist_token(jti: str, expires_in: int = 86400):
    r = get_redis()
    r.setex(f"{TOKEN_BLACKLIST_PREFIX}{jti}", expires_in, "1")


def is_token_blacklisted(jti: str) -> bool:
    r = get_redis()
    return r.exists(f"{TOKEN_BLACKLIST_PREFIX}{jti}") == 1


def blacklist_all_user_tokens(user_id: str):
    """Invalidate all sessions for a user (e.g., password change)."""
    r = get_redis()
    pattern = f"{SESSION_PREFIX}{user_id}:*"
    keys = r.keys(pattern)
    for key in keys:
        jti = r.get(key)
        if jti:
            blacklist_token(jti)
        r.delete(key)
