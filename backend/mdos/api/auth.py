"""Authentication: cloud accounts (email and password) and the desktop local session."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..config import get_settings
from ..db import get_db
from ..deps import ensure_local_owner, get_current_user, local_mode_only
from ..errors import Conflict, Forbidden, Unauthorized
from ..models import Organization, User
from ..ratelimit import limit_auth
from ..security import create_access_token, hash_password, verify_password

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


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        org_id=user.org_id,
        organization=user.organization.name if user.organization else "",
    )


@router.post("/register", response_model=TokenOut, dependencies=[Depends(limit_auth)])
def register(body: RegisterIn, db: Session = Depends(get_db)) -> TokenOut:
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
    return TokenOut(access_token=create_access_token(user.id, user.org_id), user=_user_out(user))


@router.post("/login", response_model=TokenOut, dependencies=[Depends(limit_auth)])
def login(body: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise Unauthorized("Incorrect email or password.")
    audit.record(db, org_id=user.org_id, actor_type="user", actor_id=user.id, action="auth.login",
                 entity_type="user", entity_id=user.id)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, user.org_id), user=_user_out(user))


@router.post("/local-session", response_model=TokenOut, dependencies=[Depends(local_mode_only)])
def local_session(db: Session = Depends(get_db)) -> TokenOut:
    """Desktop build only. The API is bound to loopback and protected by a trusted-host check.

    Browsers on other origins cannot read this response (no CORS grant), so they cannot obtain the
    token needed by every other endpoint.
    """
    user = ensure_local_owner(db)
    return TokenOut(access_token=create_access_token(user.id, user.org_id), user=_user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)


@router.get("/mode")
def mode() -> dict:
    settings = get_settings()
    return {"mode": settings.mdos_mode, "registration": settings.allow_registration and not settings.is_local}
