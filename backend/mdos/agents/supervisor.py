"""Supervisor: runs bounded workflows of specialist agents with persisted status, approval gates, retry and rollback.

Execution modes: ``sync`` (tests, CLI) runs in the request; ``thread`` runs in a small worker pool with a fresh
database session so long workflows expose status while they run.
"""

from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import audit
from ..config import get_settings
from ..db import session_factory, utcnow
from ..errors import Conflict, NotFound, ValidationFailed
from ..jsonutil import to_jsonable
from ..models import (
    AgentRun,
    Analysis,
    Approval,
    Dataset,
    DatasetVersion,
    Decision,
    Evidence,
    Experiment,
    Insight,
    Journey,
    Project,
    Recommendation,
    Report,
    Scenario,
    Segment,
    WorkflowRun,
    insight_evidence,
    recommendation_evidence,
)
from . import journey_agents, research_agents, strategy_agents  # noqa: F401  (register agents)
from .base import AGENTS
from .contract import AgentBlocked, AgentContext, ToolNotAuthorized
from .providers import get_provider

logger = logging.getLogger("mdos.supervisor")

WORKFLOWS: dict[str, dict[str, Any]] = {
    "research_design": {
        "label": "Research design (business question to questionnaire)",
        "module": "research",
        "steps": ["research_director", "problem_framing", "research_design", "questionnaire", "sampling", "fieldwork", "research_qa"],
        "final_gate": "adopt_design",
        "state": {"phase": "design"},
    },
    "research_analysis": {
        "label": "Research analysis (data to insight report)",
        "module": "research",
        "steps": ["research_director", "data_quality", "data_cleaning", "statistical_analysis", "price_sensitivity",
                  "segmentation", "text_analytics", "insight", "research_qa", "report"],
        "state": {"phase": "analysis"},
    },
    "strategy_baseline": {
        "label": "Strategy simulation (evidence to scenarios and decision)",
        "module": "strategy",
        "steps": ["market_model", "pricing", "media_allocation", "scenario", "strategy_narrative"],
        "state": {},
    },
    "journey_voc": {
        "label": "Journey design (reviews to interventions and experiments)",
        "module": "journey",
        "steps": ["voice_of_customer", "journey_mapping", "pain_point", "experience_opportunity", "journey_simulation",
                  "experiment_design"],
        "state": {"template": "tourism"},
    },
}

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mdos-agent")


def catalog() -> list[dict[str, Any]]:
    return [{"key": k, "label": v["label"], "module": v["module"], "steps": v["steps"],
             "final_gate": v.get("final_gate")} for k, v in WORKFLOWS.items()]


def start(db: Session, project: Project, workflow: str, user_id: str, inputs: dict[str, Any] | None = None) -> WorkflowRun:
    if workflow not in WORKFLOWS:
        raise ValidationFailed(f"Unknown workflow '{workflow}'.")
    busy = db.scalar(select(WorkflowRun).where(WorkflowRun.project_id == project.id, WorkflowRun.workflow == workflow,
                                               WorkflowRun.status.in_(("queued", "running"))))
    if busy:
        raise Conflict("This workflow is already running for the project.")
    spec = WORKFLOWS[workflow]
    run = WorkflowRun(project_id=project.id, workflow=workflow, status="queued", input=to_jsonable(inputs or {}),
                      steps=spec["steps"], current_step=0, context={**spec["state"], **(inputs or {})}, created_by=user_id)
    db.add(run)
    db.flush()
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type="user", actor_id=user_id,
                 action="workflow.start", entity_type="workflow_run", entity_id=run.id, details={"workflow": workflow})
    db.commit()
    dispatch(run.id)
    return run


def dispatch(workflow_run_id: str) -> None:
    if get_settings().execution_mode == "sync":
        execute(workflow_run_id)
    else:
        _executor.submit(execute, workflow_run_id)


def execute(workflow_run_id: str) -> None:
    """Run steps from ``current_step`` until done, failed or paused at an approval gate."""
    db = session_factory()()
    try:
        run = db.get(WorkflowRun, workflow_run_id)
        if run is None or run.status in ("succeeded", "cancelled"):
            return
        project = db.get(Project, run.project_id)
        provider = get_provider()
        run.status = "running"
        db.commit()
        state = dict(run.context or {})
        while run.current_step < len(run.steps):
            key = run.steps[run.current_step]
            agent_cls = AGENTS[key]
            agent_run = AgentRun(project_id=project.id, workflow_run_id=run.id, agent=key, step_index=run.current_step,
                                 status="running", input=to_jsonable({k: v for k, v in state.items() if not k.startswith("_")
                                                                      and k != "package"}),
                                 provider=provider.name, model=provider.model, started_at=utcnow(),
                                 attempt=1 + (db.scalar(select(AgentRun.attempt).where(
                                     AgentRun.workflow_run_id == run.id, AgentRun.step_index == run.current_step)
                                     .order_by(AgentRun.attempt.desc())) or 0))
            db.add(agent_run)
            db.flush()
            state["_agent"] = key
            ctx = AgentContext(db=db, project=project, user_id=run.created_by or "", run_id=agent_run.id,
                               workflow_run_id=run.id, state=state, provider=provider, allowed_tools=agent_cls.tools)
            try:
                result = agent_cls().run(ctx)
            except (AgentBlocked, ToolNotAuthorized, ValidationFailed, NotFound) as exc:
                db.rollback()
                _fail(db, run.id, agent_run_id=None, key=key, step=run.current_step, error=str(exc), provider=provider,
                      state=state)
                return
            except Exception as exc:  # noqa: BLE001 - any agent failure is recorded and recoverable by retry
                db.rollback()
                logger.exception("Agent %s failed", key)
                _fail(db, run.id, agent_run_id=None, key=key, step=run.current_step,
                      error=f"{type(exc).__name__}: {exc}", provider=provider, state=state,
                      trace=traceback.format_exc(limit=5))
                return
            agent_run.status = result.status
            agent_run.result = to_jsonable({**result.model_dump(), "llm_calls": ctx.llm_calls})
            agent_run.finished_at = utcnow()
            audit.record(db, org_id=project.org_id, project_id=project.id, actor_type="agent", actor_id=f"agent:{key}",
                         action=f"agent.{result.status}", entity_type="agent_run", entity_id=agent_run.id,
                         details={"workflow": run.workflow, "tools": result.tools_used})
            run.current_step += 1
            run.context = to_jsonable(state)
            if result.status == "awaiting_approval":
                _request_step_approval(db, project, run, key, state)
                run.status = "awaiting_approval"
                db.commit()
                return
            db.commit()
        spec = WORKFLOWS[run.workflow]
        if spec.get("final_gate") == "adopt_design":
            from ..services import approvals

            approvals.request(db, project, action="adopt_design", entity_type="workflow_run", entity_id=run.id,
                              summary="Adopt the generated research design package", payload={"workflow_run_id": run.id},
                              requested_by="agent:research_director")
            run.status = "awaiting_approval"
        else:
            run.status = "succeeded"
            run.finished_at = utcnow()
        run.context = to_jsonable(state)
        db.commit()
    finally:
        db.close()


def _request_step_approval(db: Session, project: Project, run: WorkflowRun, key: str, state: dict[str, Any]) -> None:
    from ..services import approvals

    if key == "data_cleaning":
        req = state["cleaning_request"]
        approvals.request(db, project, action="apply_cleaning", entity_type="dataset_version", entity_id=req["parent_version_id"],
                          summary=f"Apply {len(req['operations'])} cleaning operation(s) (workflow step)",
                          payload={"operations": req["operations"], "run_id": run.id, "workflow_run_id": run.id},
                          requested_by="agent:data_cleaning")


def _fail(db: Session, workflow_run_id: str, *, agent_run_id: str | None, key: str, step: int, error: str, provider: Any,
          state: dict[str, Any], trace: str = "") -> None:
    run = db.get(WorkflowRun, workflow_run_id)
    project = db.get(Project, run.project_id)
    attempt = 1 + (db.scalar(select(AgentRun.attempt).where(AgentRun.workflow_run_id == run.id, AgentRun.step_index == step)
                             .order_by(AgentRun.attempt.desc())) or 0)
    db.add(AgentRun(project_id=project.id, workflow_run_id=run.id, agent=key, step_index=step, status="failed", error=error,
                    provider=provider.name, model=provider.model, attempt=attempt, started_at=utcnow(), finished_at=utcnow(),
                    result={"task_id": "", "status": "failed", "inputs_used": [], "actions_taken": [], "tools_used": [],
                            "evidence": [], "assumptions": [], "uncertainties": [error], "outputs": {"trace": trace},
                            "recommended_next_step": "Fix the cause and retry this step."}))
    run.status = "failed"
    run.error = error
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type="agent", actor_id=f"agent:{key}",
                 action="agent.failed", entity_type="workflow_run", entity_id=run.id, details={"error": error[:500]})
    db.commit()


def resume(db: Session, run: WorkflowRun, user_id: str) -> WorkflowRun:
    if run.status not in ("awaiting_approval", "failed"):
        raise Conflict(f"Workflow is {run.status}; nothing to resume.")
    if run.status == "awaiting_approval" and run.current_step >= len(run.steps):
        raise Conflict("Workflow is waiting for its final approval.")
    run.status = "queued"
    run.error = ""
    audit.record(db, org_id=db.get(Project, run.project_id).org_id, project_id=run.project_id, actor_type="user",
                 actor_id=user_id, action="workflow.resume", entity_type="workflow_run", entity_id=run.id)
    db.commit()
    dispatch(run.id)
    return run


def retry(db: Session, run: WorkflowRun, user_id: str) -> WorkflowRun:
    if run.status != "failed":
        raise Conflict("Only failed workflows can be retried.")
    return resume(db, run, user_id)


def cancel(db: Session, run: WorkflowRun, user_id: str) -> WorkflowRun:
    if run.status in ("succeeded", "cancelled"):
        raise Conflict(f"Workflow is already {run.status}.")
    run.status = "cancelled"
    run.finished_at = utcnow()
    for a in db.scalars(select(Approval).where(Approval.entity_id == run.id, Approval.status == "pending")).all():
        a.status = "rejected"
        a.rationale = "Workflow cancelled"
    audit.record(db, org_id=db.get(Project, run.project_id).org_id, project_id=run.project_id, actor_type="user",
                 actor_id=user_id, action="workflow.cancel", entity_type="workflow_run", entity_id=run.id)
    db.commit()
    return run


def rollback(db: Session, run: WorkflowRun, user_id: str) -> dict[str, int]:
    """Remove draft rows the workflow created. Approved or decided items are kept and block nothing else."""
    project = db.get(Project, run.project_id)
    rid = run.id
    counts: dict[str, int] = {}
    if run.workflow == "research_design":
        from ..services.research import rollback_design

        counts.update(rollback_design(db, project, rid, user_id))
    for model in (Insight, Recommendation):
        rows = db.scalars(select(model).where(model.project_id == project.id, model.source_run_id == rid,
                                              model.status == "draft")).all()
        for r in rows:
            db.delete(r)
        counts[model.__tablename__] = len(rows)
    rows = db.scalars(select(Report).where(Report.project_id == project.id, Report.source_run_id == rid, Report.status == "draft")).all()
    for r in rows:
        db.delete(r)
    counts["reports"] = len(rows)
    db.flush()
    removed_ev = 0
    for ev in db.scalars(select(Evidence).where(Evidence.project_id == project.id, Evidence.source_run_id == rid)).all():
        used = db.execute(select(insight_evidence.c.insight_id).where(insight_evidence.c.evidence_id == ev.id)).first() or \
            db.execute(select(recommendation_evidence.c.recommendation_id).where(recommendation_evidence.c.evidence_id == ev.id)).first()
        if not used:
            db.delete(ev)
            removed_ev += 1
    counts["evidence"] = removed_ev
    db.flush()
    db.execute(delete(Segment).where(Segment.project_id == project.id, Segment.source_run_id == rid))
    removed_an = 0
    for a in db.scalars(select(Analysis).where(Analysis.project_id == project.id, Analysis.source_run_id == rid)).all():
        if not db.scalar(select(Evidence.id).where(Evidence.analysis_id == a.id)):
            db.delete(a)
            removed_an += 1
    counts["analyses"] = removed_an
    for d in db.scalars(select(Decision).where(Decision.project_id == project.id, Decision.status == "proposed")).all():
        scenario = db.get(Scenario, d.scenario_id) if d.scenario_id else None
        if scenario and scenario.source_run_id == rid:
            db.delete(d)
    db.flush()
    scenarios = db.scalars(select(Scenario).where(Scenario.project_id == project.id, Scenario.source_run_id == rid,
                                                  Scenario.status != "adopted")).all()
    for s in sorted(scenarios, key=lambda s: s.kind != "scenario"):
        db.delete(s)
    counts["scenarios"] = len(scenarios)
    exps = db.scalars(select(Experiment).where(Experiment.project_id == project.id, Experiment.source_run_id == rid,
                                               Experiment.status == "draft")).all()
    for x in exps:
        db.delete(x)
    counts["experiments"] = len(exps)
    journeys = db.scalars(select(Journey).where(Journey.project_id == project.id, Journey.source_run_id == rid,
                                                Journey.status == "draft")).all()
    for j in journeys:
        db.delete(j)
    counts["journeys"] = len(journeys)
    for v in db.scalars(select(DatasetVersion).where(DatasetVersion.project_id == project.id, DatasetVersion.source_run_id == rid)).all():
        dataset = db.get(Dataset, v.dataset_id)
        v.status = "superseded"
        if dataset and dataset.current_version_id == v.id and v.parent_id:
            dataset.current_version_id = v.parent_id
    for a in db.scalars(select(Approval).where(Approval.project_id == project.id, Approval.status == "pending")).all():
        if a.entity_id == rid or (a.payload or {}).get("workflow_run_id") == rid:
            a.status = "rejected"
            a.rationale = "Workflow rolled back"
    run.status = "cancelled"
    run.finished_at = utcnow()
    for ar in db.scalars(select(AgentRun).where(AgentRun.workflow_run_id == rid)).all():
        ar.rolled_back = True
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type="user", actor_id=user_id,
                 action="workflow.rollback", entity_type="workflow_run", entity_id=rid, details=counts)
    db.commit()
    return counts


def adopt(db: Session, project: Project, run: WorkflowRun, user_id: str) -> dict[str, int]:
    from ..services.research import adopt_design

    if run.workflow != "research_design":
        raise ValidationFailed("Only research design workflows produce an adoptable package.")
    package = (run.context or {}).get("package")
    if not package:
        raise ValidationFailed("The workflow has no design package to adopt.")
    counts = adopt_design(db, project, package, run.id, user_id)
    run.status = "succeeded"
    run.finished_at = utcnow()
    for ar in db.scalars(select(AgentRun).where(AgentRun.workflow_run_id == run.id)).all():
        ar.applied, ar.applied_by, ar.applied_at = True, user_id, utcnow()
    return counts
