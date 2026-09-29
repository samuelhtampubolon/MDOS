"""FastAPI dependencies for authentication, tenancy and project permissions."""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .errors import Forbidden, NotFound, Unauthorized
from .models import Organization, Project, ProjectMember, User
from .security import decode_access_token

ROLE_RANK = {"viewer": 1, "editor": 2, "owner": 3}
LOCAL_OWNER_EMAIL = "owner@local.mdos"


def ensure_local_owner(db: Session) -> User:
    """Create (once) the single local organization and owner used by the desktop build."""
    user = db.scalar(select(User).where(User.email == LOCAL_OWNER_EMAIL))
    if user:
        return user
    org = Organization(name="My workspace")
    db.add(org)
    db.flush()
    user = User(org_id=org.id, email=LOCAL_OWNER_EMAIL, name="Local owner", role="owner")
    db.add(user)
    db.commit()
    return user


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("Missing bearer token.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise Unauthorized("Invalid or expired token.") from exc
    user = db.get(User, payload.get("sub"))
    if not user or not user.is_active or user.org_id != payload.get("org"):
        raise Unauthorized("Invalid or expired token.")
    return user


@dataclass
class ProjectAccess:
    project: Project
    user: User
    role: str

    def require(self, minimum: str) -> None:
        if ROLE_RANK[self.role] < ROLE_RANK[minimum]:
            raise Forbidden(f"This action needs the '{minimum}' role on the project.")

    @property
    def actor(self) -> str:
        return self.user.id


def resolve_project_access(db: Session, user: User, project_id: str) -> ProjectAccess:
    """Tenant isolation: a project outside the user's organization is reported as not found."""
    project = db.get(Project, project_id)
    if not project or project.org_id != user.org_id:
        raise NotFound("Project not found.")
    if user.role in ("owner", "admin"):
        return ProjectAccess(project=project, user=user, role="owner")
    member = db.get(ProjectMember, {"project_id": project_id, "user_id": user.id})
    if not member:
        raise NotFound("Project not found.")
    return ProjectAccess(project=project, user=user, role=member.role)


def project_access(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectAccess:
    return resolve_project_access(db, user, project_id)


def local_mode_only() -> None:
    if not get_settings().is_local:
        raise NotFound("Not available.")
