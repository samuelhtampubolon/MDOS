"""Journey Designer endpoints: journeys, VOC, touchpoints, pain points, interventions and simulation."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import ProjectAccess, project_access
from ..errors import NotFound, ValidationFailed
from ..journey import engine as jengine
from ..journey.templates import TEMPLATES
from ..jsonutil import to_jsonable
from ..models import Intervention, Journey, PainPoint, Touchpoint
from ..services import approvals
from ..services import datasets as dataset_service
from ..services import journey as svc
from .common import to_dict

router = APIRouter(prefix="/projects/{project_id}", tags=["journey"])


class JourneyIn(BaseModel):
    name: str = Field(default="Customer journey", min_length=1, max_length=200)
    template: Literal["tourism", "generic"] = "tourism"


class JourneyPatch(BaseModel):
    name: str | None = None
    stages: list[dict] | None = None
    settings: dict | None = None
    status: Literal["draft", "adopted"] | None = None


class VOCIn(BaseModel):
    dataset_version_id: str
    text_column: str
    rating_column: str | None = None


class TouchpointIn(BaseModel):
    stage_key: str
    name: str = Field(min_length=1, max_length=200)
    channel: str = ""
    description: str = ""
    owner: str = ""


class PainPointIn(BaseModel):
    stage_key: str
    title: str = Field(min_length=3, max_length=300)
    description: str = ""
    theme: str = ""
    frequency: float = Field(default=0.1, ge=0, le=1)
    severity: float = Field(default=0.5, ge=0, le=1)
    reach: float = Field(default=1.0, ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)


class PainPointPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    frequency: float | None = Field(default=None, ge=0, le=1)
    severity: float | None = Field(default=None, ge=0, le=1)
    reach: float | None = Field(default=None, ge=0, le=1)
    status: Literal["open", "addressed", "dismissed"] | None = None


class InterventionIn(BaseModel):
    stage_key: str | None = None
    pain_point_id: str | None = None
    title: str | None = None
    description: str = ""
    kind: Literal["reduce_steps", "conversion_uplift", "satisfaction_uplift"] | None = None
    params: dict = Field(default_factory=dict)
    uplift_low: float = Field(default=0.05, ge=0, le=5)
    uplift_mid: float = Field(default=0.10, ge=0, le=5)
    uplift_high: float = Field(default=0.20, ge=0, le=5)
    effort: Literal["S", "M", "L"] = "M"
    confidence: Literal["low", "medium", "high"] = "low"


class InterventionPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    params: dict | None = None
    uplift_low: float | None = Field(default=None, ge=0, le=5)
    uplift_mid: float | None = Field(default=None, ge=0, le=5)
    uplift_high: float | None = Field(default=None, ge=0, le=5)
    effort: Literal["S", "M", "L"] | None = None
    confidence: Literal["low", "medium", "high"] | None = None
    status: Literal["idea", "planned", "testing", "done", "dropped"] | None = None


def _journey_out(j: Journey) -> dict:
    data = to_dict(j)
    data["touchpoints"] = [to_dict(t) for t in j.touchpoints]
    data["pain_points"] = sorted((to_dict(p) for p in j.pain_points), key=lambda p: -p["score"])
    data["interventions"] = [to_dict(i) for i in j.interventions]
    settings = j.settings or {}
    data["simulation"] = to_jsonable(jengine.simulate(j.stages, float(settings.get("entrants", 10000)),
                                                      float(settings.get("price", 100)), settings.get("word_of_mouth")))
    return data


def _audit(db: Session, access: ProjectAccess, action: str, entity_type: str, entity_id: str, details: dict | None = None):
    audit.record(db, org_id=access.user.org_id, project_id=access.project.id, actor_type="user", actor_id=access.actor,
                 action=action, entity_type=entity_type, entity_id=entity_id, details=details)


def _child(db: Session, model, entity_id: str, journey: Journey):
    row = db.get(model, entity_id)
    if not row or row.journey_id != journey.id:
        raise NotFound(f"{model.__name__} not found.")
    return row


@router.get("/journey-templates")
def templates(access: ProjectAccess = Depends(project_access)) -> list[dict]:
    return [{"key": t["key"], "name": t["name"], "entrants": t["entrants"],
             "stages": [{"key": s["key"], "name": s["name"], "kind": s["kind"], "description": s.get("description", "")}
                        for s in t["stages"]]} for t in TEMPLATES.values()]


@router.get("/journeys")
def list_journeys(access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Journey).where(Journey.project_id == access.project.id).order_by(Journey.created_at)).all()
    return [to_dict(j) for j in rows]


@router.post("/journeys", status_code=201)
def create_journey(body: JourneyIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    j = svc.create_journey(db, access.project, name=body.name, template_key=body.template, actor_id=access.actor)
    db.commit()
    db.refresh(j)
    return _journey_out(j)


@router.get("/journeys/{journey_id}")
def get_journey(journey_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    return _journey_out(svc.get_journey(db, access.project.id, journey_id))


@router.patch("/journeys/{journey_id}")
def update_journey(journey_id: str, body: JourneyPatch, access: ProjectAccess = Depends(project_access),
                   db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    j = svc.get_journey(db, access.project.id, journey_id)
    if body.name is not None:
        j.name = body.name
    if body.status is not None:
        j.status = body.status
    if body.stages is not None:
        keys = [s.get("key") for s in body.stages]
        if sorted(keys) != sorted(s["key"] for s in j.stages):
            raise ValidationFailed("Stage keys cannot be added or removed here; edit values only.")
        for s in body.stages:
            for field in ("conversion", "rate"):
                if field in s and s[field] is not None and not 0 <= float(s[field]) <= 1:
                    raise ValidationFailed(f"Stage {s['key']}: {field} must be between 0 and 1.")
        j.stages = to_jsonable(body.stages)
    if body.settings is not None:
        j.settings = to_jsonable({**(j.settings or {}), **body.settings})
    for iv in j.interventions:
        svc.simulate_intervention(j, iv)
    _audit(db, access, "journey.update", "journey", j.id)
    db.commit()
    return _journey_out(j)


@router.delete("/journeys/{journey_id}", status_code=204)
def delete_journey(journey_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> None:
    access.require("editor")
    j = svc.get_journey(db, access.project.id, journey_id)
    db.delete(j)
    _audit(db, access, "journey.delete", "journey", journey_id)
    db.commit()


@router.post("/journeys/{journey_id}/voc")
def run_voc(journey_id: str, body: VOCIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    j = svc.get_journey(db, access.project.id, journey_id)
    version = dataset_service.get_version(db, access.project.id, body.dataset_version_id)
    svc.run_voc(db, access.project, j, version, body.text_column, body.rating_column, actor_id=access.actor)
    db.commit()
    db.refresh(j)
    return _journey_out(j)


@router.post("/journeys/{journey_id}/touchpoints", status_code=201)
def add_touchpoint(journey_id: str, body: TouchpointIn, access: ProjectAccess = Depends(project_access),
                   db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    j = svc.get_journey(db, access.project.id, journey_id)
    if body.stage_key not in {s["key"] for s in j.stages}:
        raise ValidationFailed("Unknown stage.")
    t = Touchpoint(journey_id=j.id, **body.model_dump())
    db.add(t)
    db.flush()
    _audit(db, access, "touchpoint.create", "touchpoint", t.id)
    db.commit()
    return to_dict(t)


@router.delete("/journeys/{journey_id}/touchpoints/{touchpoint_id}", status_code=204)
def delete_touchpoint(journey_id: str, touchpoint_id: str, access: ProjectAccess = Depends(project_access),
                      db: Session = Depends(get_db)) -> None:
    access.require("editor")
    j = svc.get_journey(db, access.project.id, journey_id)
    db.delete(_child(db, Touchpoint, touchpoint_id, j))
    _audit(db, access, "touchpoint.delete", "touchpoint", touchpoint_id)
    db.commit()


@router.post("/journeys/{journey_id}/pain-points", status_code=201)
def add_pain_point(journey_id: str, body: PainPointIn, access: ProjectAccess = Depends(project_access),
                   db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    j = svc.get_journey(db, access.project.id, journey_id)
    if body.stage_key not in {s["key"] for s in j.stages}:
        raise ValidationFailed("Unknown stage.")
    score = body.frequency * body.severity * body.reach * 100
    p = PainPoint(journey_id=j.id, score=score, **body.model_dump())
    db.add(p)
    db.flush()
    _audit(db, access, "pain_point.create", "pain_point", p.id)
    db.commit()
    return to_dict(p)


@router.patch("/journeys/{journey_id}/pain-points/{pain_point_id}")
def update_pain_point(journey_id: str, pain_point_id: str, body: PainPointPatch, access: ProjectAccess = Depends(project_access),
                      db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    j = svc.get_journey(db, access.project.id, journey_id)
    p = _child(db, PainPoint, pain_point_id, j)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(p, key, value)
    p.score = p.frequency * p.severity * p.reach * 100
    _audit(db, access, "pain_point.update", "pain_point", p.id)
    db.commit()
    return to_dict(p)


@router.delete("/journeys/{journey_id}/pain-points/{pain_point_id}", status_code=204)
def delete_pain_point(journey_id: str, pain_point_id: str, access: ProjectAccess = Depends(project_access),
                      db: Session = Depends(get_db)) -> None:
    access.require("editor")
    j = svc.get_journey(db, access.project.id, journey_id)
    db.delete(_child(db, PainPoint, pain_point_id, j))
    _audit(db, access, "pain_point.delete", "pain_point", pain_point_id)
    db.commit()


@router.post("/journeys/{journey_id}/interventions", status_code=201)
def add_intervention(journey_id: str, body: InterventionIn, access: ProjectAccess = Depends(project_access),
                     db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    j = svc.get_journey(db, access.project.id, journey_id)
    data = body.model_dump()
    if body.pain_point_id and not body.title:
        pp = _child(db, PainPoint, body.pain_point_id, j)
        spec = jengine.propose_intervention({"stage": pp.stage_key, "theme": pp.theme})
        if not spec:
            raise ValidationFailed("No library intervention for this pain point; describe one manually.")
        data.update({k: v for k, v in spec.items() if k in ("stage_key", "title", "description", "kind", "params", "uplift_low",
                                                             "uplift_mid", "uplift_high", "effort", "confidence")})
    if not data.get("title") or not data.get("kind") or not data.get("stage_key"):
        raise ValidationFailed("An intervention needs a stage, a title and a kind.")
    if data["stage_key"] not in {s["key"] for s in j.stages}:
        raise ValidationFailed("Unknown stage.")
    if not data["uplift_low"] <= data["uplift_mid"] <= data["uplift_high"]:
        raise ValidationFailed("Uplift estimates must satisfy low <= mid <= high.")
    iv = Intervention(journey_id=j.id, **data)
    db.add(iv)
    db.flush()
    svc.simulate_intervention(j, iv)
    _audit(db, access, "intervention.create", "intervention", iv.id)
    db.commit()
    return to_dict(iv)


@router.post("/journeys/{journey_id}/interventions/propose", status_code=201)
def propose(journey_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> list[dict]:
    access.require("editor")
    j = svc.get_journey(db, access.project.id, journey_id)
    created = svc.propose_interventions(db, access.project, j)
    for iv in created:
        _audit(db, access, "intervention.propose", "intervention", iv.id)
    db.commit()
    return [to_dict(i) for i in created]


@router.patch("/journeys/{journey_id}/interventions/{intervention_id}")
def update_intervention(journey_id: str, intervention_id: str, body: InterventionPatch,
                        access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    j = svc.get_journey(db, access.project.id, journey_id)
    iv = _child(db, Intervention, intervention_id, j)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(iv, key, value)
    if not iv.uplift_low <= iv.uplift_mid <= iv.uplift_high:
        raise ValidationFailed("Uplift estimates must satisfy low <= mid <= high.")
    svc.simulate_intervention(j, iv)
    _audit(db, access, "intervention.update", "intervention", iv.id)
    db.commit()
    return to_dict(iv)


@router.delete("/journeys/{journey_id}/interventions/{intervention_id}", status_code=204)
def delete_intervention(journey_id: str, intervention_id: str, access: ProjectAccess = Depends(project_access),
                        db: Session = Depends(get_db)) -> None:
    access.require("editor")
    j = svc.get_journey(db, access.project.id, journey_id)
    db.delete(_child(db, Intervention, intervention_id, j))
    _audit(db, access, "intervention.delete", "intervention", intervention_id)
    db.commit()


@router.post("/journeys/{journey_id}/interventions/{intervention_id}/experiment", status_code=201)
def create_experiment(journey_id: str, intervention_id: str, access: ProjectAccess = Depends(project_access),
                      db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    j = svc.get_journey(db, access.project.id, journey_id)
    iv = _child(db, Intervention, intervention_id, j)
    exp = svc.experiment_from_intervention(db, access.project, j, iv, actor_id=access.actor)
    approvals.request(db, access.project, action="launch_experiment", entity_type="experiment", entity_id=exp.id,
                      summary=f"Launch experiment: {exp.name}", requested_by=access.actor)
    db.commit()
    return to_dict(exp)
