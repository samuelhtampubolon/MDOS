"""Report builder endpoints: generate, view, export (Markdown and HTML) and finalize."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db, utcnow
from ..deps import ProjectAccess, project_access
from ..errors import ValidationFailed
from ..models import Experiment, Report
from ..reports import builder
from ..services import approvals
from .common import get_owned, to_dict

router = APIRouter(prefix="/projects/{project_id}/reports", tags=["reports"])

KINDS = Literal["research_report", "executive_summary", "decision_memo", "methods_appendix", "experiment_brief"]


class ReportIn(BaseModel):
    kind: KINDS = "research_report"
    experiment_id: str | None = None


def generate(db: Session, access: ProjectAccess, kind: str, experiment_id: str | None = None,
             source_run_id: str | None = None, actor_type: str = "user", actor_id: str | None = None) -> Report:
    if kind == "experiment_brief":
        if not experiment_id:
            raise ValidationFailed("experiment_id is required for an experiment brief.")
        experiment = get_owned(db, Experiment, experiment_id, access.project.id)
        doc = builder.build_experiment_brief(db, access.project, experiment)
    else:
        doc = builder.BUILDERS[kind](db, access.project)
    previous = db.scalars(select(Report).where(Report.project_id == access.project.id, Report.kind == kind)).all()
    report = Report(project_id=access.project.id, kind=kind, title=doc["title"], document=doc,
                    version=len(previous) + 1, evidence_ids=doc["evidence_ids"], created_by=actor_id or access.actor,
                    is_model_generated=any(b.get("model_generated") for b in doc["blocks"]), source_run_id=source_run_id)
    db.add(report)
    db.flush()
    audit.record(db, org_id=access.project.org_id, project_id=access.project.id, actor_type=actor_type,
                 actor_id=actor_id or access.actor, action="report.generate", entity_type="report", entity_id=report.id,
                 details={"kind": kind, "version": report.version})
    return report


@router.get("")
def list_reports(access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Report).where(Report.project_id == access.project.id).order_by(Report.created_at.desc())).all()
    return [to_dict(r, exclude={"document"}) for r in rows]


@router.post("", status_code=201)
def create_report(body: ReportIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    report = generate(db, access, body.kind, body.experiment_id)
    db.commit()
    return to_dict(report)


@router.get("/{report_id}")
def get_report(report_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    return to_dict(get_owned(db, Report, report_id, access.project.id))


@router.get("/{report_id}/export")
def export_report(report_id: str, format: Literal["md", "html"] = "html", access: ProjectAccess = Depends(project_access),
                  db: Session = Depends(get_db)) -> Response:
    report = get_owned(db, Report, report_id, access.project.id)
    slug = "".join(ch if ch.isalnum() else "_" for ch in report.title.lower())[:50]
    if format == "md":
        return Response(builder.to_markdown(report.document), media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{slug}.md"'})
    return Response(builder.to_html(report.document), media_type="text/html; charset=utf-8",
                    headers={"Content-Disposition": f'inline; filename="{slug}.html"'})


@router.post("/{report_id}/finalize")
def finalize(report_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    report = get_owned(db, Report, report_id, access.project.id)
    report.status = "final"
    report.finalized_by = access.actor
    report.finalized_at = utcnow()
    approvals.resolve_pending(db, access.project, "finalize_report", report.id, "approved", access.actor)
    audit.record(db, org_id=access.user.org_id, project_id=access.project.id, actor_type="user", actor_id=access.actor,
                 action="report.finalize", entity_type="report", entity_id=report.id)
    db.commit()
    return to_dict(report)


@router.delete("/{report_id}", status_code=204)
def delete_report(report_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> None:
    access.require("editor")
    report = get_owned(db, Report, report_id, access.project.id)
    db.delete(report)
    audit.record(db, org_id=access.user.org_id, project_id=access.project.id, actor_type="user", actor_id=access.actor,
                 action="report.delete", entity_type="report", entity_id=report_id)
    db.commit()
