"""Evidence, insights, recommendations and the evidence graph."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..api.common import next_seq
from ..db import get_db
from ..deps import ProjectAccess, project_access
from ..errors import Conflict, ValidationFailed
from ..models import Evidence, Insight, Recommendation
from ..services import analyses as analysis_service
from ..services import approvals
from ..services import evidence as svc
from .common import get_owned, to_dict

router = APIRouter(prefix="/projects/{project_id}", tags=["evidence"])


class ManualEvidenceIn(BaseModel):
    kind: Literal["external", "user_assertion", "quote"] = "external"
    title: str = Field(min_length=3, max_length=300)
    statement: str = Field(min_length=5, max_length=4000)
    origin: Literal["external", "user_data"] = "external"
    design: Literal["external", "observational", "qualitative", "cross_sectional_survey", "experiment"] = "external"
    strength: Literal["strong", "moderate", "weak", "insufficient"] = "weak"
    citation: str = ""
    url: str = ""


class InsightIn(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    statement: str = Field(min_length=5, max_length=4000)
    evidence_ids: list[str] = Field(default_factory=list)
    implication: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"
    uncertainty: str = ""


class InsightPatch(BaseModel):
    title: str | None = None
    statement: str | None = None
    implication: str | None = None
    confidence: Literal["high", "medium", "low"] | None = None
    uncertainty: str | None = None


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    rationale: str = ""


class RecommendationIn(BaseModel):
    statement: str = Field(min_length=5, max_length=4000)
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str = ""
    module: Literal["research", "strategy", "journey"] = "research"
    priority: Literal["high", "medium", "low"] = "medium"


def _insight_out(i: Insight) -> dict:
    data = to_dict(i)
    data["evidence"] = [{"id": e.id, "code": e.code, "title": e.title, "strength": e.strength} for e in i.evidence]
    return data


def _rec_out(r: Recommendation) -> dict:
    data = to_dict(r)
    data["evidence"] = [{"id": e.id, "code": e.code, "title": e.title, "strength": e.strength} for e in r.evidence]
    return data


@router.get("/evidence")
def list_evidence(access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Evidence).where(Evidence.project_id == access.project.id).order_by(Evidence.seq)).all()
    return [to_dict(e) for e in rows]


@router.post("/evidence", status_code=201)
def create_manual_evidence(body: ManualEvidenceIn, access: ProjectAccess = Depends(project_access),
                           db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    seq = next_seq(db, Evidence, access.project.id)
    ev = Evidence(project_id=access.project.id, seq=seq, code=f"E{seq}", kind=body.kind, title=body.title,
                  statement=body.statement, origin=body.origin, design=body.design, strength=body.strength,
                  source_ref={"citation": body.citation, "url": body.url}, created_by=access.actor)
    db.add(ev)
    db.flush()
    audit.record(db, org_id=access.user.org_id, project_id=access.project.id, actor_type="user", actor_id=access.actor,
                 action="evidence.create", entity_type="evidence", entity_id=ev.id, details={"code": ev.code, "manual": True})
    db.commit()
    return to_dict(ev)


@router.delete("/evidence/{evidence_id}", status_code=204)
def delete_evidence(evidence_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> None:
    access.require("editor")
    ev = get_owned(db, Evidence, evidence_id, access.project.id)
    if analysis_service.evidence_in_use(db, ev.id):
        raise Conflict("This evidence supports an insight or recommendation and cannot be deleted.")
    db.delete(ev)
    audit.record(db, org_id=access.user.org_id, project_id=access.project.id, actor_type="user", actor_id=access.actor,
                 action="evidence.delete", entity_type="evidence", entity_id=evidence_id)
    db.commit()


@router.get("/evidence-graph")
def graph(access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    return svc.evidence_graph(db, access.project)


@router.get("/insights")
def list_insights(access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Insight).where(Insight.project_id == access.project.id).order_by(Insight.seq)).all()
    return [_insight_out(i) for i in rows]


@router.post("/insights", status_code=201)
def create_insight(body: InsightIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    insight = svc.create_insight(db, access.project, title=body.title, statement=body.statement, evidence_ids=body.evidence_ids,
                                 implication=body.implication, confidence=body.confidence, uncertainty=body.uncertainty,
                                 actor_id=access.actor)
    db.commit()
    return _insight_out(insight)


@router.patch("/insights/{insight_id}")
def update_insight(insight_id: str, body: InsightPatch, access: ProjectAccess = Depends(project_access),
                   db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    insight = get_owned(db, Insight, insight_id, access.project.id)
    if insight.status == "approved":
        raise ValidationFailed("Approved insights are locked. Create a new insight to revise it.")
    changes = body.model_dump(exclude_unset=True)
    text = f"{changes.get('title', insight.title)} {changes.get('statement', insight.statement)}"
    svc.check_causal_language(text, insight.evidence)
    for key, value in changes.items():
        setattr(insight, key, value)
    if changes:
        insight.is_model_generated = False  # a person has edited it
    audit.record(db, org_id=access.user.org_id, project_id=access.project.id, actor_type="user", actor_id=access.actor,
                 action="insight.update", entity_type="insight", entity_id=insight.id, details={"fields": sorted(changes)})
    db.commit()
    return _insight_out(insight)


@router.post("/insights/{insight_id}/decide")
def decide_insight(insight_id: str, body: DecisionIn, access: ProjectAccess = Depends(project_access),
                   db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    insight = get_owned(db, Insight, insight_id, access.project.id)
    svc.decide_insight(db, access.project, insight, body.decision, access.actor, body.rationale)
    approvals.resolve_pending(db, access.project, "approve_insight", insight.id, body.decision, access.actor, body.rationale)
    db.commit()
    return _insight_out(insight)


@router.get("/recommendations")
def list_recommendations(access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Recommendation).where(Recommendation.project_id == access.project.id).order_by(Recommendation.seq)).all()
    return [_rec_out(r) for r in rows]


@router.post("/recommendations", status_code=201)
def create_recommendation(body: RecommendationIn, access: ProjectAccess = Depends(project_access),
                          db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    rec = svc.create_recommendation(db, access.project, statement=body.statement, evidence_ids=body.evidence_ids,
                                    rationale=body.rationale, module=body.module, priority=body.priority, actor_id=access.actor)
    db.commit()
    return _rec_out(rec)


@router.post("/recommendations/{rec_id}/decide")
def decide_recommendation(rec_id: str, body: DecisionIn, access: ProjectAccess = Depends(project_access),
                          db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    rec = get_owned(db, Recommendation, rec_id, access.project.id)
    svc.decide_recommendation(db, access.project, rec, body.decision, access.actor, body.rationale)
    approvals.resolve_pending(db, access.project, "approve_recommendation", rec.id, body.decision, access.actor, body.rationale)
    db.commit()
    return _rec_out(rec)
