from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt
import jwt

from api.constants import (
    OSS_ACCESS_TOKEN_MINUTES,
    OSS_JWT_SECRET,
    OSS_REFRESH_TOKEN_DAYS,
)

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"
TOKEN_TYPE_MFA = "mfa_challenge"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _encode(payload: dict) -> str:
    return jwt.encode(payload, OSS_JWT_SECRET, algorithm="HS256")


def create_jwt_token(user_id: int, email: str) -> str:
    return create_access_token(user_id, email)


def create_access_token(user_id: int, email: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": email,
        "typ": TOKEN_TYPE_ACCESS,
        "exp": now + timedelta(minutes=OSS_ACCESS_TOKEN_MINUTES),
        "iat": now,
    }
    return _encode(payload)


def create_refresh_token(user_id: int, email: str, jti: str | None = None) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": email,
        "typ": TOKEN_TYPE_REFRESH,
        "jti": jti or uuid4().hex,
        "exp": now + timedelta(days=OSS_REFRESH_TOKEN_DAYS),
        "iat": now,
    }
    return _encode(payload)


def create_mfa_challenge_token(user_id: int, email: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": email,
        "typ": TOKEN_TYPE_MFA,
        "exp": now + timedelta(minutes=5),
        "iat": now,
    }
    return _encode(payload)


def decode_jwt_token(token: str, *, expected_type: str | None = TOKEN_TYPE_ACCESS) -> dict:
    payload = jwt.decode(token, OSS_JWT_SECRET, algorithms=["HS256"])
    token_type = payload.get("typ", TOKEN_TYPE_ACCESS)
    if expected_type is not None and token_type != expected_type:
        raise jwt.InvalidTokenError(f"Unexpected token type {token_type}")
    return payload
