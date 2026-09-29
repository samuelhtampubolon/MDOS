"""Password hashing, JWT access tokens and the browser session cookie.

Browsers keep the session in an HttpOnly, SameSite=Strict cookie that page scripts cannot read. State-changing
requests authenticated by that cookie must also carry the ``X-Requested-With: mdos`` header, which other sites
cannot add without a CORS grant (CSRF defense). API clients may send ``Authorization: Bearer`` instead.

Tokens carry the account's session version (bumped by "sign out everywhere") and, in the desktop build, a
fingerprint of the per-launch key, so closing MDOS ends every session it issued.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from starlette.requests import Request
from starlette.responses import Response

from .config import get_settings

_hasher = PasswordHasher()  # Argon2id with library defaults
ALGORITHM = "HS256"
SESSION_COOKIE = "mdos_session"
SECURE_SESSION_COOKIE = "__Host-mdos_session"
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "mdos"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: str, org_id: str, minutes: int | None = None, version: int = 0) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "org": org_id,
        "ver": version,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes or settings.access_token_minutes)).timestamp()),
        "typ": "access",
    }
    tag = launch_tag()
    if tag:
        payload["lt"] = tag
    return jwt.encode(payload, settings.resolved_secret_key(), algorithm=ALGORITHM)


def launch_tag() -> str | None:
    """Desktop build: a short fingerprint of the per-launch key (``None`` when no key is in use)."""
    settings = get_settings()
    if not (settings.is_local and settings.mdos_local_key):
        return None
    return hashlib.sha256(settings.mdos_local_key.encode("utf-8")).hexdigest()[:16]


def _cookie_secure(request: Request) -> bool:
    configured = get_settings().cookie_secure
    return configured if configured is not None else request.url.scheme == "https"


def session_cookie_name(request: Request) -> str:
    """``__Host-`` prefixed over HTTPS (locked to this exact host). Over plain loopback HTTP the port is part of
    the name, because browsers share cookies across ports and two desktop instances must not overwrite each other.
    """
    if _cookie_secure(request):
        return SECURE_SESSION_COOKIE
    port = request.url.port
    return f"{SESSION_COOKIE}_{port}" if port else SESSION_COOKIE


def set_session_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(session_cookie_name(request), token, max_age=get_settings().access_token_minutes * 60,
                        path="/", httponly=True, secure=_cookie_secure(request), samesite="strict")


def clear_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(session_cookie_name(request), path="/", httponly=True, secure=_cookie_secure(request),
                           samesite="strict")


def decode_access_token(token: str) -> dict:
    """Decode and validate a token. Raises ``jwt.PyJWTError`` on any problem."""
    settings = get_settings()
    payload = jwt.decode(token, settings.resolved_secret_key(), algorithms=[ALGORITHM])
    if payload.get("typ") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return payload
