"""Analysis studio endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ProjectAccess, project_access
from ..models import Analysis
from ..services import analyses as svc
from ..services import datasets as dataset_service
from .common import get_owned, to_dict

router = APIRouter(prefix="/projects/{project_id}/analyses", tags=["analyses"])


class AnalysisIn(BaseModel):
    dataset_version_id: str
    method: str
    params: dict = Field(default_factory=dict)
    title: str = ""


class EvidenceKeysIn(BaseModel):
    keys: list[str] = Field(default_factory=list)


@router.get("")
def list_analyses(access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Analysis).where(Analysis.project_id == access.project.id).order_by(Analysis.created_at.desc())).all()
    return [{**to_dict(a, exclude={"result"}), "summary": (a.result or {}).get("summary", "")} for a in rows]


@router.post("", status_code=201)
def run(body: AnalysisIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    version = dataset_service.get_version(db, access.project.id, body.dataset_version_id)
    analysis = svc.run_analysis(db, access.project, version, body.method, body.params, actor_id=access.actor, title=body.title)
    db.commit()
    return to_dict(analysis)


@router.get("/{analysis_id}")
def get_analysis(analysis_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    return to_dict(get_owned(db, Analysis, analysis_id, access.project.id))


@router.post("/{analysis_id}/evidence", status_code=201)
def save_evidence(analysis_id: str, body: EvidenceKeysIn, access: ProjectAccess = Depends(project_access),
                  db: Session = Depends(get_db)) -> list[dict]:
    access.require("editor")
    analysis = get_owned(db, Analysis, analysis_id, access.project.id)
    rows = svc.evidence_from_analysis(db, access.project, analysis, body.keys or None, actor_id=access.actor)
    db.commit()
    return [to_dict(e) for e in rows]


@router.delete("/{analysis_id}", status_code=204)
def delete(analysis_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> None:
    access.require("editor")
    analysis = get_owned(db, Analysis, analysis_id, access.project.id)
    svc.delete_analysis(db, access.project, analysis, access.actor)
    db.commit()
