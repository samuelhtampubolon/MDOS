"""Approvals inbox: every human gate in one place."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ProjectAccess, project_access
from ..models import Approval
from ..services import approval_handlers  # noqa: F401  (registers handlers)
from ..services import approvals as svc
from .common import get_owned, to_dict

router = APIRouter(prefix="/projects/{project_id}/approvals", tags=["approvals"])


class DecideIn(BaseModel):
    decision: Literal["approved", "rejected"]
    rationale: str = ""


@router.get("")
def list_approvals(status: str | None = "pending", access: ProjectAccess = Depends(project_access),
                   db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(Approval).where(Approval.project_id == access.project.id)
    if status:
        stmt = stmt.where(Approval.status == status)
    return [to_dict(a) for a in db.scalars(stmt.order_by(Approval.requested_at.desc())).all()]


@router.post("/{approval_id}/decide")
def decide(approval_id: str, body: DecideIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    approval = get_owned(db, Approval, approval_id, access.project.id)
    outcome = svc.decide(db, access.project, approval, body.decision, access.actor, body.rationale)
    db.commit()
    return {"approval": to_dict(approval), "outcome": outcome}
