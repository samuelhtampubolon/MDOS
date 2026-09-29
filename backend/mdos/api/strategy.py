"""Strategy Simulator endpoints: baseline model, scenarios, analyses and the decision log."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import ProjectAccess, project_access
from ..errors import ValidationFailed
from ..jsonutil import to_jsonable
from ..models import Decision, Scenario
from ..services import approvals
from ..services import strategy as svc
from ..strategy import analysis as strat
from ..strategy.engine import LEVER_TYPES
from .common import get_owned, to_dict

router = APIRouter(prefix="/projects/{project_id}", tags=["strategy"])


class BaselineIn(BaseModel):
    name: str = "Baseline"
    model: dict | None = None
    with_what_ifs: bool = True


class ScenarioIn(BaseModel):
    baseline_id: str
    name: str = Field(min_length=1, max_length=200)
    levers: list[dict] = Field(min_length=1, max_length=20)
    description: str = ""


class ScenarioPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    model: dict | None = None
    levers: list[dict] | None = None


class OptimizeIn(BaseModel):
    total_budget: float | None = Field(default=None, gt=0)
    metric: Literal["profit", "customers", "revenue"] = "profit"


class DecisionIn(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    decision: str = Field(min_length=3, max_length=4000)
    rationale: str = ""
    scenario_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class DecideIn(BaseModel):
    approve: bool
    rationale: str = ""


def _scenario_out(s: Scenario) -> dict:
    return to_dict(s)


@router.get("/strategy/research-inputs")
def research_inputs(access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    return svc.research_inputs(db, access.project)


@router.get("/strategy/lever-types")
def lever_types(access: ProjectAccess = Depends(project_access)) -> list[str]:
    return sorted(LEVER_TYPES)


@router.get("/scenarios")
def list_scenarios(access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Scenario).where(Scenario.project_id == access.project.id).order_by(Scenario.created_at)).all()
    return [_scenario_out(s) for s in rows]


@router.post("/scenarios/baseline", status_code=201)
def create_baseline(body: BaselineIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    if body.model:
        model = svc.validate_model(body.model)
    else:
        model, _ = svc.build_default_model(db, access.project)
    baseline = svc.create_baseline(db, access.project, model, name=body.name, actor_id=access.actor)
    children = svc.graph1_what_ifs(db, access.project, baseline, actor_id=access.actor) if body.with_what_ifs else []
    db.commit()
    return {"baseline": _scenario_out(baseline), "scenarios": [_scenario_out(c) for c in children]}


@router.post("/scenarios", status_code=201)
def create_scenario(body: ScenarioIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    baseline = svc.get_scenario(db, access.project.id, body.baseline_id)
    scenario = svc.create_scenario(db, access.project, baseline, name=body.name, levers=body.levers,
                                   description=body.description, actor_id=access.actor)
    db.commit()
    return _scenario_out(scenario)


@router.get("/scenarios/compare")
def compare(ids: str = Query(..., description="Comma-separated scenario IDs"), access: ProjectAccess = Depends(project_access),
            db: Session = Depends(get_db)) -> dict:
    rows = [svc.get_scenario(db, access.project.id, i) for i in ids.split(",") if i]
    if len(rows) < 2:
        raise ValidationFailed("Select at least two scenarios.")
    keys = ("customers", "revenue", "profit", "spend", "romi", "cac", "clv", "price")
    return {"scenarios": [{"id": s.id, "name": s.name, "kind": s.kind,
                           "kpis": {k: (s.results or {}).get("kpis", {}).get(k) for k in keys}} for s in rows]}


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    return _scenario_out(svc.get_scenario(db, access.project.id, scenario_id))


@router.patch("/scenarios/{scenario_id}")
def update_scenario(scenario_id: str, body: ScenarioPatch, access: ProjectAccess = Depends(project_access),
                    db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    s = svc.get_scenario(db, access.project.id, scenario_id)
    if body.name is not None:
        s.name = body.name
    if body.description is not None:
        s.description = body.description
    refreshed = 0
    if s.kind == "baseline" and body.model is not None:
        model = svc.validate_model(body.model)
        s.model = to_jsonable(model.model_dump())
        s.results = svc.run_baseline(model)
        refreshed = svc.refresh_children(db, s)
    if s.kind == "scenario" and body.levers is not None:
        baseline = svc.get_scenario(db, access.project.id, s.baseline_id)
        resolved, results = svc.run_scenario(svc.validate_model(baseline.model), body.levers)
        s.levers, s.model, s.results = to_jsonable(body.levers), to_jsonable(resolved.model_dump()), results
    audit.record(db, org_id=access.user.org_id, project_id=access.project.id, actor_type="user", actor_id=access.actor,
                 action="scenario.update", entity_type="scenario", entity_id=s.id, details={"refreshed_children": refreshed})
    db.commit()
    return _scenario_out(s)


@router.delete("/scenarios/{scenario_id}", status_code=204)
def delete_scenario(scenario_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> None:
    access.require("editor")
    s = svc.get_scenario(db, access.project.id, scenario_id)
    db.delete(s)
    audit.record(db, org_id=access.user.org_id, project_id=access.project.id, actor_type="user", actor_id=access.actor,
                 action="scenario.delete", entity_type="scenario", entity_id=scenario_id)
    db.commit()


@router.get("/scenarios/{scenario_id}/sensitivity")
def sensitivity(scenario_id: str, metric: Literal["profit", "revenue", "customers"] = "profit", pct: float = 0.2,
                access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    s = svc.get_scenario(db, access.project.id, scenario_id)
    if not 0.01 <= pct <= 0.9:
        raise ValidationFailed("pct must be between 0.01 and 0.9.")
    return to_jsonable(strat.sensitivity(svc.validate_model(s.model), metric, pct))


@router.get("/scenarios/{scenario_id}/monte-carlo")
def monte_carlo(scenario_id: str, n: int = 1000, seed: int = 7, access: ProjectAccess = Depends(project_access),
                db: Session = Depends(get_db)) -> dict:
    s = svc.get_scenario(db, access.project.id, scenario_id)
    return to_jsonable(strat.monte_carlo(svc.validate_model(s.model), n, seed))


@router.get("/scenarios/{scenario_id}/price-curve")
def price_curve(scenario_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    s = svc.get_scenario(db, access.project.id, scenario_id)
    out = strat.price_curve(svc.validate_model(s.model))
    out["research"] = svc.research_inputs(db, access.project).get("vw_range")
    return to_jsonable(out)


@router.post("/scenarios/{scenario_id}/optimize-media")
def optimize_media(scenario_id: str, body: OptimizeIn, access: ProjectAccess = Depends(project_access),
                   db: Session = Depends(get_db)) -> dict:
    s = svc.get_scenario(db, access.project.id, scenario_id)
    return to_jsonable(strat.optimize_media(svc.validate_model(s.model), body.total_budget, metric=body.metric))


# ---- decision log ------------------------------------------------------------------------------


@router.get("/decisions")
def list_decisions(access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Decision).where(Decision.project_id == access.project.id).order_by(Decision.created_at.desc())).all()
    return [to_dict(d) for d in rows]


@router.post("/decisions", status_code=201)
def create_decision(body: DecisionIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    d = svc.create_decision(db, access.project, title=body.title, decision=body.decision, rationale=body.rationale,
                            scenario_id=body.scenario_id, evidence_ids=body.evidence_ids, actor_id=access.actor)
    approvals.request(db, access.project, action="approve_decision", entity_type="decision", entity_id=d.id,
                      summary=f"Decision: {d.title}", requested_by=access.actor)
    db.commit()
    return to_dict(d)


@router.post("/decisions/{decision_id}/decide")
def decide(decision_id: str, body: DecideIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    d = get_owned(db, Decision, decision_id, access.project.id)
    svc.decide_decision(db, access.project, d, body.approve, access.actor, body.rationale)
    approvals.resolve_pending(db, access.project, "approve_decision", d.id, "approved" if body.approve else "rejected",
                              access.actor, body.rationale)
    db.commit()
    return to_dict(d)
