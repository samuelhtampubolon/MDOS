"""Report generation use case shared by the API and the Report agent."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..errors import NotFound, ValidationFailed
from ..models import Experiment, Project, Report
from ..reports import builder


def generate(db: Session, project: Project, kind: str, *, actor_id: str, actor_type: str = "user",
             experiment_id: str | None = None, source_run_id: str | None = None) -> Report:
    if kind == "experiment_brief":
        if not experiment_id:
            raise ValidationFailed("experiment_id is required for an experiment brief.")
        experiment = db.get(Experiment, experiment_id)
        if not experiment or experiment.project_id != project.id:
            raise NotFound("Experiment not found.")
        doc = builder.build_experiment_brief(db, project, experiment)
    elif kind in builder.BUILDERS:
        doc = builder.BUILDERS[kind](db, project)
    else:
        raise ValidationFailed(f"Unknown report kind '{kind}'.")
    previous = db.scalars(select(Report.id).where(Report.project_id == project.id, Report.kind == kind)).all()
    report = Report(project_id=project.id, kind=kind, title=doc["title"], document=doc, version=len(previous) + 1,
                    evidence_ids=doc["evidence_ids"], created_by=actor_id,
                    is_model_generated=any(b.get("model_generated") for b in doc["blocks"]), source_run_id=source_run_id)
    db.add(report)
    db.flush()
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type=actor_type, actor_id=actor_id,
                 action="report.generate", entity_type="report", entity_id=report.id,
                 details={"kind": kind, "version": report.version})
    return report
