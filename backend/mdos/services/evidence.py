"""Insights, recommendations, hypothesis verdicts and the evidence graph, with quality gates enforced."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..api.common import next_seq
from ..db import utcnow
from ..errors import NotFound, QualityGateViolation, ValidationFailed
from ..models import (
    Analysis,
    Dataset,
    DatasetVersion,
    Decision,
    Evidence,
    Experiment,
    Hypothesis,
    Insight,
    Journey,
    PainPoint,
    Project,
    Recommendation,
    Scenario,
)
from ..research.language import causal_terms, suggest_associational

VERDICTS = {"supported", "not_supported", "inconclusive"}


def load_evidence(db: Session, project_id: str, evidence_ids: list[str]) -> list[Evidence]:
    ids = list(dict.fromkeys(evidence_ids))
    if not ids:
        return []
    rows = db.scalars(select(Evidence).where(Evidence.project_id == project_id, Evidence.id.in_(ids))).all()
    if len(rows) != len(ids):
        raise NotFound("One or more evidence records were not found in this project.")
    return sorted(rows, key=lambda e: e.seq)


def check_causal_language(text: str, evidence: list[Evidence]) -> None:
    """Quality gate: no causal language unless at least one linked evidence record comes from an experiment."""
    terms = causal_terms(text)
    if terms and not any(e.design == "experiment" for e in evidence):
        raise QualityGateViolation(
            "Causal wording needs experimental evidence. The linked evidence is observational or survey-based.",
            details={"terms": terms, "suggestion": suggest_associational(text)},
        )


def create_insight(db: Session, project: Project, *, title: str, statement: str, evidence_ids: list[str],
                   implication: str = "", confidence: str = "medium", uncertainty: str = "", is_model_generated: bool = False,
                   actor_id: str, actor_type: str = "user", source_run_id: str | None = None) -> Insight:
    evidence = load_evidence(db, project.id, evidence_ids)
    if not evidence:
        raise QualityGateViolation("Every insight must cite at least one evidence record.")
    if confidence not in ("high", "medium", "low"):
        raise ValidationFailed("Confidence must be high, medium or low.")
    check_causal_language(f"{title} {statement}", evidence)
    seq = next_seq(db, Insight, project.id)
    insight = Insight(project_id=project.id, seq=seq, code=f"I{seq}", title=title[:300], statement=statement,
                      implication=implication, confidence=confidence, uncertainty=uncertainty,
                      is_model_generated=is_model_generated, created_by=actor_id, source_run_id=source_run_id)
    insight.evidence = evidence
    db.add(insight)
    db.flush()
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type=actor_type, actor_id=actor_id,
                 action="insight.create", entity_type="insight", entity_id=insight.id,
                 details={"code": insight.code, "evidence": [e.code for e in evidence], "model_generated": is_model_generated})
    return insight


def decide_insight(db: Session, project: Project, insight: Insight, decision: str, actor_id: str, rationale: str = "") -> Insight:
    if decision not in ("approved", "rejected"):
        raise ValidationFailed("Decision must be approved or rejected.")
    if decision == "approved" and not insight.evidence:
        raise QualityGateViolation("An insight without evidence cannot be approved.")
    insight.status = decision
    insight.decided_by = actor_id
    insight.decided_at = utcnow()
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type="user", actor_id=actor_id,
                 action=f"insight.{decision}", entity_type="insight", entity_id=insight.id, details={"rationale": rationale})
    return insight


def create_recommendation(db: Session, project: Project, *, statement: str, evidence_ids: list[str], rationale: str = "",
                          module: str = "research", priority: str = "medium", is_model_generated: bool = False,
                          actor_id: str, actor_type: str = "user", source_run_id: str | None = None) -> Recommendation:
    evidence = load_evidence(db, project.id, evidence_ids)
    if not evidence:
        raise QualityGateViolation("Every recommendation must cite the evidence that supports it.")
    if module not in ("research", "strategy", "journey"):
        raise ValidationFailed("Module must be research, strategy or journey.")
    check_causal_language(f"{statement} {rationale}", evidence)
    seq = next_seq(db, Recommendation, project.id)
    rec = Recommendation(project_id=project.id, seq=seq, code=f"R{seq}", statement=statement, rationale=rationale,
                         module=module, priority=priority, is_model_generated=is_model_generated, created_by=actor_id,
                         source_run_id=source_run_id)
    rec.evidence = evidence
    db.add(rec)
    db.flush()
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type=actor_type, actor_id=actor_id,
                 action="recommendation.create", entity_type="recommendation", entity_id=rec.id,
                 details={"code": rec.code, "evidence": [e.code for e in evidence]})
    return rec


def decide_recommendation(db: Session, project: Project, rec: Recommendation, decision: str, actor_id: str,
                          rationale: str = "") -> Recommendation:
    if decision not in ("approved", "rejected"):
        raise ValidationFailed("Decision must be approved or rejected.")
    rec.status = decision
    rec.decided_by = actor_id
    rec.decided_at = utcnow()
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type="user", actor_id=actor_id,
                 action=f"recommendation.{decision}", entity_type="recommendation", entity_id=rec.id,
                 details={"rationale": rationale})
    return rec


def propose_verdict(db: Session, project: Project, hypothesis: Hypothesis, verdict: str, evidence_ids: list[str],
                    rationale: str, *, actor_id: str, actor_type: str = "user") -> Hypothesis:
    """Proposed verdicts never change the final status on their own (spec quality gate)."""
    if verdict not in VERDICTS:
        raise ValidationFailed("Verdict must be supported, not_supported or inconclusive.")
    evidence = load_evidence(db, project.id, evidence_ids)
    if not evidence:
        raise QualityGateViolation("A verdict must cite the evidence it is based on.")
    hypothesis.status = f"proposed_{verdict}"
    hypothesis.verdict_evidence = [e.id for e in evidence]
    hypothesis.verdict_rationale = rationale
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type=actor_type, actor_id=actor_id,
                 action="hypothesis.verdict.propose", entity_type="hypothesis", entity_id=hypothesis.id,
                 details={"verdict": verdict, "evidence": [e.code for e in evidence]})
    return hypothesis


def decide_verdict(db: Session, project: Project, hypothesis: Hypothesis, approve: bool, actor_id: str,
                   rationale: str = "", verdict: str | None = None) -> Hypothesis:
    if not hypothesis.status.startswith("proposed_") and verdict is None:
        raise ValidationFailed("There is no proposed verdict to decide on.")
    if approve:
        final = verdict or hypothesis.status.removeprefix("proposed_")
        if final not in VERDICTS:
            raise ValidationFailed("Verdict must be supported, not_supported or inconclusive.")
        if not hypothesis.verdict_evidence:
            raise QualityGateViolation("A verdict can only be approved with linked evidence.")
        hypothesis.status = final
        hypothesis.decided_by = actor_id
        hypothesis.decided_at = utcnow()
    else:
        hypothesis.status = "untested"
    if rationale:
        hypothesis.verdict_rationale = rationale
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type="user", actor_id=actor_id,
                 action=f"hypothesis.verdict.{'approve' if approve else 'reject'}", entity_type="hypothesis",
                 entity_id=hypothesis.id, details={"status": hypothesis.status})
    return hypothesis


def evidence_graph(db: Session, project: Project) -> dict[str, Any]:
    """Nodes and edges from sources to decisions (the lineage chain, made visible)."""
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []

    def node(nid: str, kind: str, label: str, **extra: Any) -> None:
        nodes.setdefault(nid, {"id": nid, "kind": kind, "label": label, **extra})

    pid = project.id
    for ds in db.scalars(select(Dataset).where(Dataset.project_id == pid)).all():
        node(f"dataset:{ds.id}", "dataset", ds.name, origin=ds.origin)
    for v in db.scalars(select(DatasetVersion).where(DatasetVersion.project_id == pid)).all():
        node(f"version:{v.id}", "dataset_version", f"v{v.version} ({v.n_rows} rows)")
        edges.append({"from": f"version:{v.parent_id}" if v.parent_id else f"dataset:{v.dataset_id}", "to": f"version:{v.id}"})
    for a in db.scalars(select(Analysis).where(Analysis.project_id == pid)).all():
        node(f"analysis:{a.id}", "analysis", a.title or a.method, method=a.method)
        if a.dataset_version_id:
            edges.append({"from": f"version:{a.dataset_version_id}", "to": f"analysis:{a.id}"})
    for e in db.scalars(select(Evidence).where(Evidence.project_id == pid)).all():
        node(f"evidence:{e.id}", "evidence", f"{e.code} {e.title}", strength=e.strength, origin=e.origin)
        if e.analysis_id:
            edges.append({"from": f"analysis:{e.analysis_id}", "to": f"evidence:{e.id}"})
    for i in db.scalars(select(Insight).where(Insight.project_id == pid)).all():
        node(f"insight:{i.id}", "insight", f"{i.code} {i.title}", status=i.status)
        edges += [{"from": f"evidence:{e.id}", "to": f"insight:{i.id}"} for e in i.evidence]
    for r in db.scalars(select(Recommendation).where(Recommendation.project_id == pid)).all():
        node(f"recommendation:{r.id}", "recommendation", f"{r.code} {r.statement[:60]}", status=r.status)
        edges += [{"from": f"evidence:{e.id}", "to": f"recommendation:{r.id}"} for e in r.evidence]
    for h in db.scalars(select(Hypothesis).where(Hypothesis.project_id == pid)).all():
        node(f"hypothesis:{h.id}", "hypothesis", f"{h.code} {h.statement[:60]}", status=h.status)
        edges += [{"from": f"evidence:{eid}", "to": f"hypothesis:{h.id}"} for eid in (h.verdict_evidence or [])]
    for s in db.scalars(select(Scenario).where(Scenario.project_id == pid)).all():
        node(f"scenario:{s.id}", "scenario", s.name, status=s.status)
        for a in (s.model or {}).get("assumptions", []):
            if a.get("evidence_id"):
                edges.append({"from": f"evidence:{a['evidence_id']}", "to": f"scenario:{s.id}"})
    for d in db.scalars(select(Decision).where(Decision.project_id == pid)).all():
        node(f"decision:{d.id}", "decision", d.title, status=d.status)
        if d.scenario_id:
            edges.append({"from": f"scenario:{d.scenario_id}", "to": f"decision:{d.id}"})
        edges += [{"from": f"evidence:{eid}", "to": f"decision:{d.id}"} for eid in (d.evidence_ids or [])]
    for j in db.scalars(select(Journey).where(Journey.project_id == pid)).all():
        node(f"journey:{j.id}", "journey", j.name, status=j.status)
        for pp in db.scalars(select(PainPoint).where(PainPoint.journey_id == j.id)).all():
            node(f"pain_point:{pp.id}", "pain_point", pp.title, stage=pp.stage_key)
            edges.append({"from": f"pain_point:{pp.id}", "to": f"journey:{j.id}"})
            edges += [{"from": f"evidence:{eid}", "to": f"pain_point:{pp.id}"} for eid in (pp.evidence_ids or [])]
    for x in db.scalars(select(Experiment).where(Experiment.project_id == pid)).all():
        node(f"experiment:{x.id}", "experiment", x.name, status=x.status)
        if x.evidence_id:
            edges.append({"from": f"experiment:{x.id}", "to": f"evidence:{x.evidence_id}"})
    valid = set(nodes)
    edges = [e for e in edges if e["from"] in valid and e["to"] in valid]
    return {"nodes": list(nodes.values()), "edges": edges}
