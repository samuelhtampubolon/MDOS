"""Projects: the shared container that links research, strategy and journey work."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, storage
from ..db import get_db
from ..deps import ProjectAccess, get_current_user, project_access
from ..errors import NotFound, ValidationFailed
from ..models import AuditLog, Project, ProjectMember, User
from .common import to_dict

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    business_question: str = Field(min_length=10, max_length=4000)
    decision_to_inform: str = Field(default="", max_length=4000)
    context: str = Field(default="", max_length=10000)
    industry: str = Field(default="", max_length=100)
    geography: str = Field(default="Indonesia", max_length=100)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    brief: dict = Field(default_factory=dict)


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    business_question: str | None = Field(default=None, max_length=4000)
    decision_to_inform: str | None = Field(default=None, max_length=4000)
    context: str | None = Field(default=None, max_length=10000)
    industry: str | None = Field(default=None, max_length=100)
    geography: str | None = Field(default=None, max_length=100)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    status: str | None = None
    brief: dict | None = None


class MemberIn(BaseModel):
    email: str
    role: str = "editor"


def project_out(project: Project, role: str | None = None) -> dict:
    data = to_dict(project)
    if role:
        data["my_role"] = role
    return data


@router.get("")
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(Project).where(Project.org_id == user.org_id).order_by(Project.created_at.desc())
    projects = db.scalars(stmt).all()
    if user.role in ("owner", "admin"):
        return [project_out(p, "owner") for p in projects]
    memberships = {
        m.project_id: m.role
        for m in db.scalars(select(ProjectMember).where(ProjectMember.user_id == user.id)).all()
    }
    return [project_out(p, memberships[p.id]) for p in projects if p.id in memberships]


@router.post("", status_code=201)
def create_project(body: ProjectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    project = Project(
        org_id=user.org_id,
        name=body.name,
        business_question=body.business_question,
        decision_to_inform=body.decision_to_inform,
        context=body.context,
        industry=body.industry,
        geography=body.geography,
        currency=body.currency.upper(),
        brief=body.brief,
        created_by=user.id,
    )
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
    audit.record(db, org_id=user.org_id, project_id=project.id, actor_type="user", actor_id=user.id,
                 action="project.create", entity_type="project", entity_id=project.id)
    db.commit()
    return project_out(project, "owner")


@router.post("/demo", status_code=201)
def create_demo(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Create the Lake Toba demo project (synthetic data) and run the closed loop through the agents."""
    from ..services.demo import create_demo_project

    project = create_demo_project(db, user.id, user.org_id)
    db.refresh(project)
    return project_out(project, "owner")


@router.get("/{project_id}")
def get_project(access: ProjectAccess = Depends(project_access)) -> dict:
    return project_out(access.project, access.role)


@router.patch("/{project_id}")
def update_project(body: ProjectPatch, access: ProjectAccess = Depends(project_access),
                   db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    changes = body.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] not in ("active", "archived"):
        raise ValidationFailed("Status must be 'active' or 'archived'.")
    for key, value in changes.items():
        setattr(access.project, key, value.upper() if key == "currency" and value else value)
    audit.record(db, org_id=access.user.org_id, project_id=access.project.id, actor_type="user",
                 actor_id=access.actor, action="project.update", entity_type="project",
                 entity_id=access.project.id, details={"fields": sorted(changes)})
    db.commit()
    return project_out(access.project, access.role)


class DeleteProjectIn(BaseModel):
    confirm: str = Field(default="", max_length=200)


@router.delete("/{project_id}", status_code=204)
def delete_project(body: DeleteProjectIn | None = None, access: ProjectAccess = Depends(project_access),
                   db: Session = Depends(get_db)) -> None:
    """Data deletion workflow: removes every project row (cascade) and every stored file.

    Irreversible, so the request body must repeat the project name: ``{"confirm": "<project name>"}``. It is not
    a query parameter, so the name never lands in access logs.
    """
    access.require("owner")
    project = access.project
    if (body.confirm if body else "").strip() != project.name.strip():
        raise ValidationFailed("Type the project name exactly to confirm deletion.")
    org_id, project_id = project.org_id, project.id
    db.delete(project)
    audit.record(db, org_id=org_id, project_id=None, actor_type="user", actor_id=access.actor,
                 action="project.delete", entity_type="project", entity_id=project_id,
                 details={"name": project.name})
    db.commit()
    storage.delete_project_files(org_id, project_id)


@router.get("/{project_id}/members")
def list_members(access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(ProjectMember, User).join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == access.project.id)
    ).all()
    return [{"user_id": u.id, "email": u.email, "name": u.name, "role": m.role} for m, u in rows]


@router.post("/{project_id}/members", status_code=201)
def add_member(body: MemberIn, access: ProjectAccess = Depends(project_access),
               db: Session = Depends(get_db)) -> dict:
    access.require("owner")
    if body.role not in ("owner", "editor", "viewer"):
        raise ValidationFailed("Role must be owner, editor or viewer.")
    user = db.scalar(select(User).where(User.email == body.email.lower(), User.org_id == access.user.org_id))
    if not user:
        raise NotFound("No user with that email in your organization.")
    member = db.get(ProjectMember, {"project_id": access.project.id, "user_id": user.id})
    if member:
        member.role = body.role
    else:
        db.add(ProjectMember(project_id=access.project.id, user_id=user.id, role=body.role))
    audit.record(db, org_id=access.user.org_id, project_id=access.project.id, actor_type="user",
                 actor_id=access.actor, action="project.member.set", entity_type="user", entity_id=user.id,
                 details={"role": body.role})
    db.commit()
    return {"user_id": user.id, "email": user.email, "name": user.name, "role": body.role}


@router.get("/{project_id}/audit")
def project_audit(limit: int = 200, access: ProjectAccess = Depends(project_access),
                  db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(
        select(AuditLog).where(AuditLog.project_id == access.project.id)
        .order_by(AuditLog.created_at.desc()).limit(min(max(limit, 1), 1000))
    ).all()
    return [to_dict(r) for r in rows]
