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
from ..models import Report
from ..reports import builder
from ..services import approvals
from ..services import reports as report_service
from .common import get_owned, to_dict

router = APIRouter(prefix="/projects/{project_id}/reports", tags=["reports"])

KINDS = Literal["research_report", "executive_summary", "decision_memo", "methods_appendix", "experiment_brief"]
# The HTML export is a standalone page opened in its own tab: styles only, no scripts, no network, opaque origin.
EXPORT_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; " \
             "frame-ancestors 'none'; sandbox"


class ReportIn(BaseModel):
    kind: KINDS = "research_report"
    experiment_id: str | None = None


@router.get("")
def list_reports(access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Report).where(Report.project_id == access.project.id).order_by(Report.created_at.desc())).all()
    return [to_dict(r, exclude={"document"}) for r in rows]


@router.post("", status_code=201)
def create_report(body: ReportIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    report = report_service.generate(db, access.project, body.kind, actor_id=access.actor, experiment_id=body.experiment_id)
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
                    headers={"Content-Disposition": f'inline; filename="{slug}.html"', "Content-Security-Policy": EXPORT_CSP})


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
