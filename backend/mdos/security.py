"""Password hashing and JWT access tokens."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .config import get_settings

_hasher = PasswordHasher()  # Argon2id with library defaults
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: str, org_id: str, minutes: int | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "org": org_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes or settings.access_token_minutes)).timestamp()),
        "typ": "access",
    }
    return jwt.encode(payload, settings.resolved_secret_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a token. Raises ``jwt.PyJWTError`` on any problem."""
    settings = get_settings()
    payload = jwt.decode(token, settings.resolved_secret_key(), algorithms=[ALGORITHM])
    if payload.get("typ") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return payload
