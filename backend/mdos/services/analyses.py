"""Run analyses on dataset versions and turn their results into evidence (the Analyze and Evidence steps)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..analytics import registry
from ..analytics.common import AnalysisError
from ..api.common import next_seq
from ..errors import Conflict, ValidationFailed
from ..jsonutil import to_jsonable
from ..models import (
    Analysis,
    Dataset,
    DatasetVersion,
    Evidence,
    Project,
    Segment,
    insight_evidence,
    recommendation_evidence,
)
from . import datasets as dataset_service

DESIGN_BY_METHOD = {"text_themes": "qualitative", "sentiment": "qualitative"}


def run_analysis(db: Session, project: Project, version: DatasetVersion, method: str, params: dict[str, Any], *,
                 actor_id: str, actor_type: str = "user", source_run_id: str | None = None, title: str = "") -> Analysis:
    variables = dataset_service.project_variable_meta(db, project.id)
    types = dataset_service.column_types_for(version, variables)
    labels = dataset_service.labels_for(variables)
    df = dataset_service.load_version(version)
    try:
        parsed, result = registry.run(method, df, params, types=types, labels=labels, currency=project.currency)
    except AnalysisError as exc:
        raise ValidationFailed(str(exc)) from exc
    payload = result.as_dict()
    analysis = Analysis(
        project_id=project.id, dataset_version_id=version.id, method=method, title=title or result.title,
        params=to_jsonable(parsed.model_dump()), status="succeeded",
        result={"summary": payload["summary"], "data": payload["result"], "evidence_candidates": payload["evidence"],
                "charts": payload["charts"]},
        assumptions=payload["assumptions"], warnings=payload["warnings"], limitations=payload["limitations"],
        n=payload["n"], created_by=actor_id, source_run_id=source_run_id,
    )
    db.add(analysis)
    db.flush()
    if method == "segmentation":
        for seg in payload["result"]["segments"]:
            db.add(Segment(project_id=project.id, analysis_id=analysis.id, name=seg["name"], size=seg["size"],
                           share=seg["share"], profile=seg["profile"], persona=seg["persona"], source_run_id=source_run_id))
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type=actor_type, actor_id=actor_id,
                 action="analysis.run", entity_type="analysis", entity_id=analysis.id,
                 details={"method": method, "dataset_version": version.id, "n": payload["n"]})
    return analysis


def evidence_from_analysis(db: Session, project: Project, analysis: Analysis, keys: list[str] | None, *,
                           actor_id: str, actor_type: str = "user", source_run_id: str | None = None) -> list[Evidence]:
    """Copy selected evidence candidates into Evidence records. Values are copied, never re-derived."""
    candidates = analysis.result.get("evidence_candidates", [])
    if keys:
        wanted = set(keys)
        candidates = [c for c in candidates if c["key"] in wanted]
        missing = wanted - {c["key"] for c in candidates}
        if missing:
            raise ValidationFailed(f"Unknown evidence key(s): {', '.join(sorted(missing))}")
    existing = {
        (e.analysis_id, e.source_ref.get("key")): e
        for e in db.scalars(select(Evidence).where(Evidence.project_id == project.id, Evidence.analysis_id == analysis.id)).all()
    }
    version = db.get(DatasetVersion, analysis.dataset_version_id) if analysis.dataset_version_id else None
    dataset = db.get(Dataset, version.dataset_id) if version else None
    origin = dataset.origin if dataset else "user_data"
    created = []
    for cand in candidates:
        if (analysis.id, cand["key"]) in existing:
            created.append(existing[(analysis.id, cand["key"])])
            continue
        seq = next_seq(db, Evidence, project.id)
        ev = Evidence(
            project_id=project.id, seq=seq, code=f"E{seq}", kind="theme" if analysis.method == "text_themes" else "statistical",
            title=cand["title"][:300], statement=cand["statement"], analysis_id=analysis.id,
            dataset_version_id=analysis.dataset_version_id,
            source_ref={"analysis_id": analysis.id, "key": cand["key"], "method": analysis.method,
                        "dataset": dataset.name if dataset else None, "version": version.version if version else None},
            origin=origin, design=DESIGN_BY_METHOD.get(analysis.method, "cross_sectional_survey"),
            strength=cand.get("strength", "moderate"), n=cand.get("n"), effect_size=cand.get("effect_size"),
            effect_label=cand.get("effect_label") or "", p_value=cand.get("p_value"), ci_low=cand.get("ci_low"),
            ci_high=cand.get("ci_high"), value=cand.get("value") or {}, created_by=actor_id, source_run_id=source_run_id,
        )
        db.add(ev)
        db.flush()
        created.append(ev)
        audit.record(db, org_id=project.org_id, project_id=project.id, actor_type=actor_type, actor_id=actor_id,
                     action="evidence.create", entity_type="evidence", entity_id=ev.id,
                     details={"code": ev.code, "analysis": analysis.id, "key": cand["key"]})
    return created


def delete_analysis(db: Session, project: Project, analysis: Analysis, actor_id: str) -> None:
    linked = db.scalars(select(Evidence.id).where(Evidence.analysis_id == analysis.id)).all()
    if linked:
        raise Conflict("This analysis supports evidence records. Delete that evidence first.")
    db.delete(analysis)
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type="user", actor_id=actor_id,
                 action="analysis.delete", entity_type="analysis", entity_id=analysis.id)


def evidence_in_use(db: Session, evidence_id: str) -> bool:
    used = db.execute(select(insight_evidence.c.insight_id).where(insight_evidence.c.evidence_id == evidence_id)).first()
    used = used or db.execute(
        select(recommendation_evidence.c.recommendation_id).where(recommendation_evidence.c.evidence_id == evidence_id)).first()
    return bool(used)
