"""Experiments: backlog, sizing, launch approval and results that become research evidence."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..analytics.common import AnalysisError
from ..db import get_db
from ..deps import ProjectAccess, project_access
from ..errors import ValidationFailed
from ..models import Experiment
from ..services import approvals
from ..services import journey as svc
from .common import get_owned, to_dict

router = APIRouter(prefix="/projects/{project_id}/experiments", tags=["experiments"])


class ExperimentIn(BaseModel):
    name: str = Field(min_length=3, max_length=300)
    hypothesis: str = Field(min_length=5, max_length=2000)
    primary_metric: str = Field(min_length=2, max_length=200)
    baseline_rate: float = Field(gt=0, lt=1)
    mde: float = Field(gt=0, le=5, description="Relative minimum detectable effect")
    alpha: float = Field(default=0.05, gt=0, lt=0.5)
    power: float = Field(default=0.8, gt=0.5, lt=1)
    expected_daily_traffic: int = Field(default=0, ge=0)
    variants: list[dict] = Field(default_factory=lambda: [{"name": "Control"}, {"name": "Treatment"}])


class ExperimentPatch(BaseModel):
    name: str | None = None
    hypothesis: str | None = None
    baseline_rate: float | None = Field(default=None, gt=0, lt=1)
    mde: float | None = Field(default=None, gt=0, le=5)
    expected_daily_traffic: int | None = Field(default=None, ge=0)
    variants: list[dict] | None = None


class DecideIn(BaseModel):
    approve: bool


class ResultsIn(BaseModel):
    control_visitors: int = Field(gt=0)
    control_conversions: int = Field(ge=0)
    treatment_visitors: int = Field(gt=0)
    treatment_conversions: int = Field(ge=0)


@router.get("")
def list_experiments(access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Experiment).where(Experiment.project_id == access.project.id).order_by(Experiment.created_at.desc())).all()
    return [to_dict(x) for x in rows]


@router.post("", status_code=201)
def create_experiment(body: ExperimentIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    exp = Experiment(project_id=access.project.id, source_type="manual", created_by=access.actor, **body.model_dump())
    try:
        svc.size_experiment(exp)
    except AnalysisError as exc:
        raise ValidationFailed(str(exc)) from exc
    db.add(exp)
    db.flush()
    approvals.request(db, access.project, action="launch_experiment", entity_type="experiment", entity_id=exp.id,
                      summary=f"Launch experiment: {exp.name}", requested_by=access.actor)
    audit.record(db, org_id=access.user.org_id, project_id=access.project.id, actor_type="user", actor_id=access.actor,
                 action="experiment.create", entity_type="experiment", entity_id=exp.id)
    db.commit()
    return to_dict(exp)


@router.get("/{experiment_id}")
def get_experiment(experiment_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    return to_dict(get_owned(db, Experiment, experiment_id, access.project.id))


@router.patch("/{experiment_id}")
def update_experiment(experiment_id: str, body: ExperimentPatch, access: ProjectAccess = Depends(project_access),
                      db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    exp = get_owned(db, Experiment, experiment_id, access.project.id)
    if exp.status not in ("draft",):
        raise ValidationFailed("Only draft experiments can be edited.")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(exp, key, value)
    try:
        svc.size_experiment(exp)
    except AnalysisError as exc:
        raise ValidationFailed(str(exc)) from exc
    audit.record(db, org_id=access.user.org_id, project_id=access.project.id, actor_type="user", actor_id=access.actor,
                 action="experiment.update", entity_type="experiment", entity_id=exp.id)
    db.commit()
    return to_dict(exp)


@router.post("/{experiment_id}/decide")
def decide(experiment_id: str, body: DecideIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    exp = get_owned(db, Experiment, experiment_id, access.project.id)
    svc.decide_experiment(db, access.project, exp, body.approve, access.actor)
    approvals.resolve_pending(db, access.project, "launch_experiment", exp.id, "approved" if body.approve else "rejected", access.actor)
    db.commit()
    return to_dict(exp)


@router.post("/{experiment_id}/results")
def results(experiment_id: str, body: ResultsIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    exp = get_owned(db, Experiment, experiment_id, access.project.id)
    if body.control_conversions > body.control_visitors or body.treatment_conversions > body.treatment_visitors:
        raise ValidationFailed("Conversions cannot exceed visitors.")
    ev = svc.record_results(db, access.project, exp, actor_id=access.actor, **body.model_dump())
    db.commit()
    return {"experiment": to_dict(exp), "evidence": to_dict(ev)}


@router.delete("/{experiment_id}", status_code=204)
def delete_experiment(experiment_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> None:
    access.require("editor")
    exp = get_owned(db, Experiment, experiment_id, access.project.id)
    if exp.evidence_id:
        raise ValidationFailed("Completed experiments that produced evidence cannot be deleted.")
    db.delete(exp)
    audit.record(db, org_id=access.user.org_id, project_id=access.project.id, actor_type="user", actor_id=access.actor,
                 action="experiment.delete", entity_type="experiment", entity_id=experiment_id)
    db.commit()
