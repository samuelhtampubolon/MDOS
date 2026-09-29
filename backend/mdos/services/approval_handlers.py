"""Handlers that run when a person approves or rejects a pending approval."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..db import utcnow
from ..errors import NotFound
from ..models import Approval, DatasetVersion, Hypothesis, Insight, Project, Recommendation, Report
from . import datasets as dataset_service
from . import evidence as evidence_service
from .approvals import handler


@handler("apply_cleaning")
def _apply_cleaning(db: Session, project: Project, approval: Approval, decision: str) -> dict[str, Any]:
    if decision != "approved":
        return {"applied": False}
    parent = db.get(DatasetVersion, approval.entity_id)
    if not parent or parent.project_id != project.id:
        raise NotFound("Dataset version not found.")
    user_id = approval.decided_by or approval.requested_by
    version = dataset_service.derive_version(db, project, parent, approval.payload.get("operations", []),
                                             user_id=user_id, approved_by=user_id,
                                             source_run_id=approval.payload.get("run_id"))
    return {"applied": True, "version_id": version.id, "version": version.version, "rows": version.n_rows}


@handler("approve_insight")
def _approve_insight(db: Session, project: Project, approval: Approval, decision: str) -> dict[str, Any]:
    insight = db.get(Insight, approval.entity_id)
    if not insight or insight.project_id != project.id:
        raise NotFound("Insight not found.")
    evidence_service.decide_insight(db, project, insight, decision, approval.decided_by or "system")
    return {"insight": insight.code, "status": insight.status}


@handler("approve_recommendation")
def _approve_recommendation(db: Session, project: Project, approval: Approval, decision: str) -> dict[str, Any]:
    rec = db.get(Recommendation, approval.entity_id)
    if not rec or rec.project_id != project.id:
        raise NotFound("Recommendation not found.")
    evidence_service.decide_recommendation(db, project, rec, decision, approval.decided_by or "system")
    return {"recommendation": rec.code, "status": rec.status}


@handler("approve_verdict")
def _approve_verdict(db: Session, project: Project, approval: Approval, decision: str) -> dict[str, Any]:
    h = db.get(Hypothesis, approval.entity_id)
    if not h or h.project_id != project.id:
        raise NotFound("Hypothesis not found.")
    evidence_service.decide_verdict(db, project, h, decision == "approved", approval.decided_by or "system")
    return {"hypothesis": h.code, "status": h.status}


@handler("finalize_report")
def _finalize_report(db: Session, project: Project, approval: Approval, decision: str) -> dict[str, Any]:
    report = db.get(Report, approval.entity_id)
    if not report or report.project_id != project.id:
        raise NotFound("Report not found.")
    if decision == "approved":
        report.status = "final"
        report.finalized_by = approval.decided_by
        report.finalized_at = utcnow()
    return {"report": report.id, "status": report.status}


@handler("approve_decision")
def _approve_decision(db: Session, project: Project, approval: Approval, decision: str) -> dict[str, Any]:
    from ..models import Decision
    from . import strategy as strategy_service

    d = db.get(Decision, approval.entity_id)
    if not d or d.project_id != project.id:
        raise NotFound("Decision not found.")
    strategy_service.decide_decision(db, project, d, decision == "approved", approval.decided_by or "system")
    return {"decision": d.id, "status": d.status}


@handler("launch_experiment")
def _launch_experiment(db: Session, project: Project, approval: Approval, decision: str) -> dict[str, Any]:
    from ..models import Experiment
    from . import journey as journey_service

    exp = db.get(Experiment, approval.entity_id)
    if not exp or exp.project_id != project.id:
        raise NotFound("Experiment not found.")
    journey_service.decide_experiment(db, project, exp, decision == "approved", approval.decided_by or "system")
    return {"experiment": exp.id, "status": exp.status}
