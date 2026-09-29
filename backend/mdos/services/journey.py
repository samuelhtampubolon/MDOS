"""Journey and experiment use cases: VOC to pain points to interventions to experiments to evidence."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..analytics.power import ab_sample_size, two_proportion_test
from ..api.common import next_seq
from ..db import utcnow
from ..errors import NotFound, ValidationFailed
from ..journey import engine as jengine
from ..journey.templates import stages_for, template
from ..jsonutil import to_jsonable
from ..models import (
    Analysis,
    DatasetVersion,
    Evidence,
    Experiment,
    Intervention,
    Journey,
    PainPoint,
    Project,
    Scenario,
    Touchpoint,
)
from ..research.design import parse_question
from . import analyses as analysis_service


def journey_price(db: Session, project: Project) -> float:
    baseline = db.scalars(select(Scenario).where(Scenario.project_id == project.id, Scenario.kind == "baseline")
                          .order_by(Scenario.created_at.desc())).first()
    if baseline and (baseline.model or {}).get("offer", {}).get("price"):
        return float(baseline.model["offer"]["price"])
    parsed = parse_question(project.business_question, project.currency, project.industry)
    return float(parsed.price or 100.0)


def create_journey(db: Session, project: Project, *, name: str, template_key: str, actor_id: str, actor_type: str = "user",
                   source_run_id: str | None = None) -> Journey:
    try:
        tpl = template(template_key)
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc
    journey = Journey(project_id=project.id, name=name, template=template_key, stages=stages_for(template_key),
                      settings={"entrants": tpl["entrants"], "price": journey_price(db, project),
                                "word_of_mouth": tpl["word_of_mouth"], "entrants_source": "template default (assumption)"},
                      source_run_id=source_run_id)
    db.add(journey)
    db.flush()
    for stage in tpl["stages"]:
        for tp in stage.get("touchpoints", []):
            db.add(Touchpoint(journey_id=journey.id, stage_key=stage["key"], name=tp["name"], channel=tp.get("channel", ""),
                              source_run_id=source_run_id))
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type=actor_type, actor_id=actor_id,
                 action="journey.create", entity_type="journey", entity_id=journey.id, details={"template": template_key})
    return journey


def get_journey(db: Session, project_id: str, journey_id: str) -> Journey:
    j = db.get(Journey, journey_id)
    if not j or j.project_id != project_id:
        raise NotFound("Journey not found.")
    return j


def run_voc(db: Session, project: Project, journey: Journey, version: DatasetVersion, text_column: str,
            rating_column: str | None, *, actor_id: str, actor_type: str = "user", source_run_id: str | None = None) -> Analysis:
    params = {"text_column": text_column, "template": journey.template}
    if rating_column:
        params["rating_column"] = rating_column
    analysis = analysis_service.run_analysis(db, project, version, "journey_voc", params, actor_id=actor_id,
                                             actor_type=actor_type, source_run_id=source_run_id)
    evidence = analysis_service.evidence_from_analysis(db, project, analysis, None, actor_id=actor_id, actor_type=actor_type,
                                                       source_run_id=source_run_id)
    apply_voc(db, project, journey, analysis, evidence, source_run_id=source_run_id)
    return analysis


def apply_voc(db: Session, project: Project, journey: Journey, analysis: Analysis, evidence: list[Evidence],
              source_run_id: str | None = None) -> None:
    data = analysis.result["data"]
    by_stage = {s["key"]: s for s in data["stages"]}
    stages = []
    for s in journey.stages:
        v = by_stage.get(s["key"])
        s = dict(s)
        if v:
            s.update({"emotion": v["emotion"], "mentions": v["mentions"], "negative_share": v["negative_share"],
                      "top_positive": v["top_positive"], "top_negative": v["top_negative"]})
        stages.append(s)
    journey.stages = to_jsonable(stages)
    journey.voc = to_jsonable({"analysis_id": analysis.id, "summary": analysis.result["summary"], "heatmap": data["heatmap"],
                               "coverage": data["coverage"], "rating_correlation": data["rating_correlation"]})
    journey.voc_dataset_version_id = analysis.dataset_version_id
    ev_by_key = {(e.source_ref or {}).get("key"): e.id for e in evidence}
    linked = {iv.pain_point_id for iv in journey.interventions}
    for pp in list(journey.pain_points):
        # Replace earlier VOC-derived pain points; keep manual ones and those already linked to interventions.
        if pp.evidence_ids and pp.status == "open" and pp.id not in linked:
            db.delete(pp)
    for p in jengine.prioritize(data["pain_points"]):
        ev_id = ev_by_key.get(f"voc:{p['stage']}:{p['theme']}")
        db.add(PainPoint(journey_id=journey.id, stage_key=p["stage"], title=p["title"], theme=p["theme"],
                         description=f"{p['mentions']} reviews mention this problem.", mentions=p["mentions"],
                         frequency=p["frequency"], severity=p["severity"], reach=p["reach"], score=p["score"],
                         evidence_ids=[ev_id] if ev_id else [], quotes=p["quotes"], source_run_id=source_run_id))


def propose_interventions(db: Session, project: Project, journey: Journey, *, limit: int = 4,
                          source_run_id: str | None = None) -> list[Intervention]:
    existing = {(i.pain_point_id, i.title) for i in journey.interventions}
    created = []
    pains = sorted(journey.pain_points, key=lambda p: -p.score)
    for pp in pains:
        if len(created) >= limit:
            break
        spec = jengine.propose_intervention({"stage": pp.stage_key, "theme": pp.theme})
        if not spec or (pp.id, spec["title"]) in existing:
            continue
        iv = Intervention(journey_id=journey.id, pain_point_id=pp.id, stage_key=spec["stage_key"], title=spec["title"],
                          description=spec["description"], kind=spec["kind"], params=spec["params"],
                          uplift_low=spec["uplift_low"], uplift_mid=spec["uplift_mid"], uplift_high=spec["uplift_high"],
                          effort=spec["effort"], confidence=spec["confidence"], source_run_id=source_run_id)
        db.add(iv)
        db.flush()
        simulate_intervention(journey, iv)
        created.append(iv)
    return created


def intervention_dict(iv: Intervention) -> dict[str, Any]:
    return {"stage_key": iv.stage_key, "kind": iv.kind, "params": iv.params or {}, "title": iv.title,
            "description": iv.description, "uplift_low": iv.uplift_low, "uplift_mid": iv.uplift_mid, "uplift_high": iv.uplift_high}


def simulate_intervention(journey: Journey, iv: Intervention) -> dict[str, Any]:
    settings = journey.settings or {}
    try:
        sim = jengine.simulate_intervention(journey.stages, intervention_dict(iv), float(settings.get("entrants", 10000)),
                                            float(settings.get("price", 100)), settings.get("word_of_mouth"))
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc
    iv.simulation = to_jsonable(sim)
    return iv.simulation


def experiment_from_intervention(db: Session, project: Project, journey: Journey, iv: Intervention, *, actor_id: str,
                                 actor_type: str = "user", source_run_id: str | None = None) -> Experiment:
    spec = jengine.experiment_for(intervention_dict(iv), journey.stages, float((journey.settings or {}).get("entrants", 10000)))
    exp = Experiment(project_id=project.id, name=spec["name"], source_type="journey_intervention", source_id=iv.id,
                     hypothesis=spec["hypothesis"], primary_metric=spec["primary_metric"], baseline_rate=spec["baseline_rate"],
                     mde=spec["mde"], alpha=spec["alpha"], power=spec["power"], sample_size_per_arm=spec["sample_size_per_arm"],
                     expected_daily_traffic=spec["expected_daily_traffic"], duration_days=spec["duration_days"],
                     variants=spec["variants"], results={"notes": spec.get("notes", [])}, created_by=actor_id,
                     source_run_id=source_run_id)
    db.add(exp)
    db.flush()
    iv.status = "planned" if iv.status == "idea" else iv.status
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type=actor_type, actor_id=actor_id,
                 action="experiment.create", entity_type="experiment", entity_id=exp.id, details={"intervention": iv.id})
    return exp


def size_experiment(exp: Experiment) -> None:
    size = ab_sample_size(exp.baseline_rate, exp.mde, exp.alpha, exp.power)
    exp.sample_size_per_arm = size["n_per_arm"]
    if exp.expected_daily_traffic:
        exp.duration_days = int(-(-2 * size["n_per_arm"] // exp.expected_daily_traffic))


def record_results(db: Session, project: Project, exp: Experiment, *, control_visitors: int, control_conversions: int,
                   treatment_visitors: int, treatment_conversions: int, actor_id: str) -> Evidence:
    """Analyze an A/B test and store the result as experimental evidence (the loop back to research)."""
    if exp.status not in ("running", "approved", "completed"):
        raise ValidationFailed("Launch the experiment (approval) before recording results.")
    res = two_proportion_test(control_conversions, control_visitors, treatment_conversions, treatment_visitors)
    lift = res["relative_lift"]
    verdict = "improved" if res["significant"] and res["difference"] > 0 else (
        "worsened" if res["significant"] and res["difference"] < 0 else "showed no significant change in")
    summary = (f"The treatment {verdict} {exp.primary_metric.lower()}: {res['p2']:.1%} versus {res['p1']:.1%} in control "
               f"(difference {res['difference'] * 100:+.1f} points, 95% CI {res['ci_low'] * 100:+.1f} to {res['ci_high'] * 100:+.1f}; "
               f"relative lift {lift:+.0%}; p = {res['p_value']:.3f}; n = {control_visitors + treatment_visitors})."
               if lift is not None else f"Treatment {res['p2']:.1%} versus control {res['p1']:.1%}.")
    seq = next_seq(db, Evidence, project.id)
    ev = Evidence(project_id=project.id, seq=seq, code=f"E{seq}", kind="experiment", title=f"Experiment result: {exp.name}"[:300],
                  statement=summary, origin="experiment", design="experiment",
                  strength="strong" if res["significant"] and min(control_visitors, treatment_visitors) >= exp.sample_size_per_arm
                  else ("moderate" if res["significant"] else "insufficient"),
                  n=control_visitors + treatment_visitors, effect_size=res["difference"], effect_label="difference in rate",
                  p_value=res["p_value"], ci_low=res["ci_low"], ci_high=res["ci_high"],
                  source_ref={"experiment_id": exp.id, "key": f"experiment:{exp.id}"}, value=to_jsonable(res),
                  created_by=actor_id)
    db.add(ev)
    db.flush()
    exp.results = to_jsonable({**(exp.results or {}), **res, "summary": summary, "control_visitors": control_visitors,
                               "control_conversions": control_conversions, "treatment_visitors": treatment_visitors,
                               "treatment_conversions": treatment_conversions,
                               "underpowered": min(control_visitors, treatment_visitors) < exp.sample_size_per_arm})
    exp.evidence_id = ev.id
    exp.status = "completed"
    if exp.source_type == "journey_intervention" and exp.source_id:
        iv = db.get(Intervention, exp.source_id)
        if iv:
            iv.status = "done" if res["significant"] and res["difference"] > 0 else "testing"
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type="user", actor_id=actor_id,
                 action="experiment.results", entity_type="experiment", entity_id=exp.id, details={"evidence": ev.code})
    return ev


def decide_experiment(db: Session, project: Project, exp: Experiment, approve: bool, actor_id: str) -> Experiment:
    if exp.status != "draft":
        raise ValidationFailed("Only draft experiments can be launched or rejected.")
    exp.status = "running" if approve else "cancelled"
    exp.decided_by = actor_id
    exp.decided_at = utcnow()
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type="user", actor_id=actor_id,
                 action="experiment.launch" if approve else "experiment.cancel", entity_type="experiment", entity_id=exp.id)
    return exp
