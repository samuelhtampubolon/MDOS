"""Agents and workflows: registry, provider status, start, status, resume, retry, cancel and rollback."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents import supervisor
from ..agents.base import registry
from ..agents.providers import provider_status
from ..db import get_db
from ..deps import ProjectAccess, get_current_user, project_access
from ..models import AgentRun, WorkflowRun
from ..ratelimit import limit_agents
from .common import get_owned, to_dict

router = APIRouter(tags=["agents"])


class WorkflowIn(BaseModel):
    workflow: Literal["research_design", "research_analysis", "strategy_baseline", "journey_voc"]
    inputs: dict = Field(default_factory=dict)


ALLOWED_INPUTS = {"dataset_id", "reviews_dataset_id", "text_column", "rating_column", "template", "journey_name"}


def _run_out(db: Session, run: WorkflowRun, with_steps: bool = True) -> dict:
    data = to_dict(run, exclude={"context"})
    ctx = run.context or {}
    data["has_package"] = bool(ctx.get("package"))
    if with_steps:
        runs = db.scalars(select(AgentRun).where(AgentRun.workflow_run_id == run.id)
                          .order_by(AgentRun.step_index, AgentRun.attempt)).all()
        latest: dict[int, AgentRun] = {}
        for r in runs:
            latest[r.step_index] = r
        data["step_runs"] = [
            {"index": i, "agent": key, "status": (latest[i].status if i in latest else
                                                  ("pending" if i >= run.current_step else "skipped")),
             "agent_run_id": latest[i].id if i in latest else None,
             "summary": (latest[i].result or {}).get("actions_taken", [])[-1:] if i in latest else [],
             "error": latest[i].error if i in latest else ""}
            for i, key in enumerate(run.steps)
        ]
        if ctx.get("package"):
            pkg = ctx["package"]
            data["package_preview"] = {
                "objectives": (pkg.get("framing") or {}).get("objectives", []),
                "hypotheses": [h["statement"] for h in (pkg.get("design") or {}).get("hypotheses", [])],
                "constructs": [c["name"] for c in (pkg.get("design") or {}).get("constructs", [])],
                "question_count": len((pkg.get("questionnaire") or {}).get("questions", [])),
                "sample_size": ((pkg.get("sampling") or {}).get("sample_size") or {}).get("recommended"),
                "qa": (pkg.get("qa") or {}).get("checks", []),
            }
    return data


@router.get("/agents")
def agents(_user=Depends(get_current_user)) -> dict:
    return registry()


@router.get("/agents/provider")
def provider(_user=Depends(get_current_user)) -> dict:
    return provider_status()


@router.get("/workflows")
def workflows(_user=Depends(get_current_user)) -> list[dict]:
    return supervisor.catalog()


@router.post("/projects/{project_id}/workflows", status_code=202, dependencies=[Depends(limit_agents)])
def start_workflow(body: WorkflowIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    inputs = {k: v for k, v in body.inputs.items() if k in ALLOWED_INPUTS}
    run = supervisor.start(db, access.project, body.workflow, access.actor, inputs)
    db.refresh(run)
    return _run_out(db, run)


@router.get("/projects/{project_id}/workflows")
def list_workflows(access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(WorkflowRun).where(WorkflowRun.project_id == access.project.id)
                      .order_by(WorkflowRun.created_at.desc())).all()
    return [_run_out(db, r, with_steps=False) for r in rows]


@router.get("/projects/{project_id}/workflows/{run_id}")
def get_workflow(run_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    return _run_out(db, get_owned(db, WorkflowRun, run_id, access.project.id))


@router.post("/projects/{project_id}/workflows/{run_id}/{action}")
def control(run_id: str, action: Literal["resume", "retry", "cancel", "rollback"], access: ProjectAccess = Depends(project_access),
            db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    run = get_owned(db, WorkflowRun, run_id, access.project.id)
    outcome = {}
    if action == "resume":
        supervisor.resume(db, run, access.actor)
    elif action == "retry":
        supervisor.retry(db, run, access.actor)
    elif action == "cancel":
        supervisor.cancel(db, run, access.actor)
    else:
        outcome = supervisor.rollback(db, run, access.actor)
    db.refresh(run)
    return {**_run_out(db, run), "outcome": outcome}


@router.get("/projects/{project_id}/agent-runs")
def list_agent_runs(access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(AgentRun).where(AgentRun.project_id == access.project.id)
                      .order_by(AgentRun.created_at.desc()).limit(200)).all()
    return [to_dict(r, exclude={"input"}) for r in rows]


@router.get("/projects/{project_id}/agent-runs/{agent_run_id}")
def get_agent_run(agent_run_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    return to_dict(get_owned(db, AgentRun, agent_run_id, access.project.id))
