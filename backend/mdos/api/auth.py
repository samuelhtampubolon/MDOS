"""Authentication: cloud accounts (email and password) and the desktop local session.

Every successful sign-in sets the HttpOnly session cookie used by the web app. The token is also returned in the
body for API clients that prefer ``Authorization: Bearer``; the web app never stores it.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..config import get_settings
from ..db import get_db
from ..deps import ensure_local_owner, get_current_user, local_mode_only, require_csrf_header
from ..errors import Conflict, Forbidden, Unauthorized
from ..models import Organization, User
from ..ratelimit import limit_auth
from ..security import (
    clear_session_cookie,
    create_access_token,
    hash_password,
    session_cookie_name,
    set_session_cookie,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    organization: str = Field(min_length=1, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    org_id: str
    organization: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth token type, not a secret
    user: UserOut


class LocalSessionIn(BaseModel):
    key: str | None = Field(default=None, max_length=200)


def _session(request: Request, response: Response, user: User) -> TokenOut:
    token = create_access_token(user.id, user.org_id, version=user.session_version or 0)
    set_session_cookie(response, request, token)
    return TokenOut(access_token=token, user=_user_out(user))


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        org_id=user.org_id,
        organization=user.organization.name if user.organization else "",
    )


# Sign-in endpoints also need the CSRF header, so another site cannot sign a visitor in to a different account.
@router.post("/register", response_model=TokenOut, dependencies=[Depends(limit_auth), Depends(require_csrf_header)])
def register(body: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)) -> TokenOut:
    settings = get_settings()
    if settings.is_local:
        raise Forbidden("Registration is not used in local mode.")
    if not settings.allow_registration:
        raise Forbidden("Registration is disabled on this server.")
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise Conflict("An account with this email already exists.")
    org = Organization(name=body.organization)
    db.add(org)
    db.flush()
    user = User(
        org_id=org.id, email=email, name=body.name, password_hash=hash_password(body.password), role="owner"
    )
    db.add(user)
    db.flush()
    audit.record(db, org_id=org.id, actor_type="user", actor_id=user.id, action="auth.register",
                 entity_type="user", entity_id=user.id)
    db.commit()
    db.refresh(user)
    return _session(request, response, user)


@router.post("/login", response_model=TokenOut, dependencies=[Depends(limit_auth), Depends(require_csrf_header)])
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise Unauthorized("Incorrect email or password.")
    audit.record(db, org_id=user.org_id, actor_type="user", actor_id=user.id, action="auth.login",
                 entity_type="user", entity_id=user.id)
    db.commit()
    return _session(request, response, user)


@router.post("/local-session", response_model=TokenOut,
             dependencies=[Depends(local_mode_only), Depends(limit_auth), Depends(require_csrf_header)])
def local_session(request: Request, response: Response, body: LocalSessionIn | None = None,
                  db: Session = Depends(get_db)) -> TokenOut:
    """Desktop build only: loopback-bound, trusted-host checked, and (when launched with ``mdos``) gated by a
    per-launch key, so other accounts or programs on the same computer cannot open a session.
    """
    expected = get_settings().mdos_local_key
    if expected and not hmac.compare_digest((body.key if body else "") or "", expected):
        raise Unauthorized("Open MDOS from the link shown in the MDOS window.")
    return _session(request, response, ensure_local_owner(db))


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf_header)])
def logout(request: Request, response: Response) -> None:
    """End this browser session (clears the cookie)."""
    if request.cookies.get(session_cookie_name(request)):
        clear_session_cookie(response, request)


@router.post("/logout-all", status_code=204)
def logout_all(request: Request, response: Response, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)) -> None:
    """Invalidate every token issued to this account, on every device."""
    user.session_version = (user.session_version or 0) + 1
    audit.record(db, org_id=user.org_id, actor_type="user", actor_id=user.id, action="auth.logout_all",
                 entity_type="user", entity_id=user.id)
    db.commit()
    clear_session_cookie(response, request)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)


@router.get("/mode")
def mode() -> dict:
    settings = get_settings()
    return {"mode": settings.mdos_mode, "registration": settings.allow_registration and not settings.is_local,
            "local_key_required": settings.is_local and bool(settings.mdos_local_key)}
