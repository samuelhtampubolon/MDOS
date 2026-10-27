"""Strategy use cases: research inputs for the market model, scenarios, decisions."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import utcnow
from ..errors import NotFound, ValidationFailed
from ..jsonutil import to_jsonable
from ..models import Analysis, Dataset, Decision, Evidence, Project, Scenario
from ..research.design import parse_question
from ..strategy import analysis as strat
from ..strategy.defaults import default_model, graph1_scenarios
from ..strategy.engine import apply_levers, describe_lever, simulate
from ..strategy.model import MarketModel
from . import datasets as dataset_service


def _latest(db: Session, project_id: str, method: str, where=None) -> Analysis | None:
    stmt = select(Analysis).where(Analysis.project_id == project_id, Analysis.method == method)
    rows = db.scalars(stmt.order_by(Analysis.created_at.desc())).all()
    for a in rows:
        if where is None or where(a):
            return a
    return None


def _evidence_id(db: Session, analysis: Analysis | None, key_prefix: str) -> str | None:
    if not analysis:
        return None
    for e in db.scalars(select(Evidence).where(Evidence.analysis_id == analysis.id)).all():
        if (e.source_ref or {}).get("key", "").startswith(key_prefix):
            return e.id
    return None


def research_inputs(db: Session, project: Project) -> dict[str, Any]:
    """Collect the research evidence that can feed the market model, with evidence IDs for citation."""
    parsed = parse_question(project.business_question, project.currency, project.industry)
    inputs: dict[str, Any] = {"currency": project.currency, "tourism": parsed.tourism, "target_price": parsed.price,
                              "offering": parsed.offering, "sources": []}
    gg = _latest(db, project.id, "gabor_granger")
    if gg:
        inputs["price_points"] = gg.result["data"]["price_response"]
        inputs["price_points_evidence_id"] = _evidence_id(db, gg, "gg:")
        inputs["sources"].append({"input": "price_points", "analysis_id": gg.id, "evidence_id": inputs["price_points_evidence_id"]})
    wtp = _latest(db, project.id, "wtp", where=lambda a: a.result["data"].get("groups"))
    if wtp:
        groups = wtp.result["data"]["groups"]
        inputs["wtp_by_group"] = [{"group": g["group"], "share": g["share"], "n": g["n"]} for g in groups]
        total = sum(g["n"] for g in groups) or 1
        inputs["group_shares"] = {g["group"]: g["n"] / total for g in groups}
        inputs["wtp_by_group_evidence_id"] = _evidence_id(db, wtp, "wtp:")
        inputs["group_shares_evidence_id"] = inputs["wtp_by_group_evidence_id"]
        inputs["sources"].append({"input": "wtp_by_group", "analysis_id": wtp.id, "evidence_id": inputs["wtp_by_group_evidence_id"]})
    vw = _latest(db, project.id, "van_westendorp")
    if vw:
        d = vw.result["data"]
        inputs["vw_range"] = {"pmc": d.get("pmc"), "pme": d.get("pme"), "opp": d.get("opp"), "ipp": d.get("ipp")}
        inputs["vw_evidence_id"] = _evidence_id(db, vw, "vw:range")
        inputs["sources"].append({"input": "vw_range", "analysis_id": vw.id, "evidence_id": inputs["vw_evidence_id"]})
    survey = db.scalars(select(Dataset).where(Dataset.project_id == project.id, Dataset.kind == "survey")
                        .order_by(Dataset.created_at)).first()
    if survey and survey.current_version_id:
        version = dataset_service.current_version(db, survey)
        cols = {c["name"] for c in version.columns}
        if "age_group" in cols or "AU" in cols:
            df = dataset_service.load_version(version)
            if "age_group" in df.columns:
                ages = df["age_group"].dropna().astype(str)
                if len(ages):
                    inputs["genz_share"] = float((ages == "18-24").mean())
            if "AU" in df.columns:
                inputs["authenticity"] = float(df["AU"].dropna().mean())
    return to_jsonable(inputs)


def build_default_model(db: Session, project: Project) -> tuple[MarketModel, dict[str, Any]]:
    inputs = research_inputs(db, project)
    model = default_model(name=project.name, offering=inputs.get("offering") or project.name, currency=project.currency,
                          tourism=bool(inputs.get("tourism")), inputs=inputs)
    return model, inputs


def validate_model(data: dict[str, Any]) -> MarketModel:
    try:
        return MarketModel.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        raise ValidationFailed(f"Invalid market model: {first['msg']} at {'.'.join(str(x) for x in first['loc'])}") from exc


def run_baseline(model: MarketModel) -> dict[str, Any]:
    results = simulate(model)
    results["break_even_price"] = strat.break_even_price(model)
    results["positioning"] = strat.positioning_map(model)
    return to_jsonable(results)


def run_scenario(baseline: MarketModel, levers: list[dict[str, Any]]) -> tuple[MarketModel, dict[str, Any]]:
    try:
        resolved = apply_levers(baseline, levers)
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc
    base_res = simulate(baseline)
    res = simulate(resolved)
    res["comparison"] = strat.compare(base_res, res)
    res["waterfall"] = strat.waterfall(baseline, levers)
    res["lever_descriptions"] = [describe_lever(lv, baseline) for lv in levers]
    res["break_even_price"] = strat.break_even_price(resolved)
    res["positioning"] = strat.positioning_map(resolved)
    return resolved, to_jsonable(res)


def create_baseline(db: Session, project: Project, model: MarketModel, *, name: str, actor_id: str, actor_type: str = "user",
                    source_run_id: str | None = None, status: str = "draft") -> Scenario:
    scenario = Scenario(project_id=project.id, name=name, kind="baseline", model=to_jsonable(model.model_dump()),
                        results=run_baseline(model), created_by=actor_id, source_run_id=source_run_id, status=status)
    db.add(scenario)
    db.flush()
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type=actor_type, actor_id=actor_id,
                 action="scenario.baseline.create", entity_type="scenario", entity_id=scenario.id)
    return scenario


def create_scenario(db: Session, project: Project, baseline: Scenario, *, name: str, levers: list[dict[str, Any]],
                    description: str = "", actor_id: str, actor_type: str = "user", source_run_id: str | None = None) -> Scenario:
    if baseline.kind != "baseline":
        raise ValidationFailed("Scenarios must start from a baseline.")
    base_model = validate_model(baseline.model)
    resolved, results = run_scenario(base_model, levers)
    scenario = Scenario(project_id=project.id, name=name, kind="scenario", baseline_id=baseline.id, description=description,
                        model=to_jsonable(resolved.model_dump()), levers=to_jsonable(levers), results=results,
                        created_by=actor_id, source_run_id=source_run_id)
    db.add(scenario)
    db.flush()
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type=actor_type, actor_id=actor_id,
                 action="scenario.create", entity_type="scenario", entity_id=scenario.id, details={"levers": levers})
    return scenario


def refresh_children(db: Session, baseline: Scenario) -> int:
    base_model = validate_model(baseline.model)
    children = db.scalars(select(Scenario).where(Scenario.baseline_id == baseline.id)).all()
    for child in children:
        resolved, results = run_scenario(base_model, child.levers or [])
        child.model = to_jsonable(resolved.model_dump())
        child.results = results
    return len(children)


def graph1_what_ifs(db: Session, project: Project, baseline: Scenario, *, actor_id: str, actor_type: str = "user",
                    source_run_id: str | None = None) -> list[Scenario]:
    model = validate_model(baseline.model)
    target = parse_question(project.business_question, project.currency).price
    created = []
    for spec in graph1_scenarios(model, target):
        created.append(create_scenario(db, project, baseline, name=spec["name"], levers=spec["levers"], actor_id=actor_id,
                                       actor_type=actor_type, source_run_id=source_run_id))
    return created


def get_scenario(db: Session, project_id: str, scenario_id: str) -> Scenario:
    s = db.get(Scenario, scenario_id)
    if not s or s.project_id != project_id:
        raise NotFound("Scenario not found.")
    return s


def create_decision(db: Session, project: Project, *, title: str, decision: str, rationale: str, scenario_id: str | None,
                    evidence_ids: list[str], actor_id: str, actor_type: str = "user") -> Decision:
    if scenario_id:
        get_scenario(db, project.id, scenario_id)
    if evidence_ids:
        found = db.scalars(select(Evidence.id).where(Evidence.project_id == project.id, Evidence.id.in_(evidence_ids))).all()
        if len(set(found)) != len(set(evidence_ids)):
            raise NotFound("One or more evidence records were not found in this project.")
    d = Decision(project_id=project.id, title=title, decision=decision, rationale=rationale, scenario_id=scenario_id,
                 evidence_ids=list(dict.fromkeys(evidence_ids)), created_by=actor_id)
    db.add(d)
    db.flush()
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type=actor_type, actor_id=actor_id,
                 action="decision.propose", entity_type="decision", entity_id=d.id)
    return d


def decide_decision(db: Session, project: Project, d: Decision, approve: bool, actor_id: str, rationale: str = "") -> Decision:
    d.status = "approved" if approve else "rejected"
    d.decided_by = actor_id
    d.decided_at = utcnow()
    if rationale:
        d.rationale = (d.rationale + "\n" if d.rationale else "") + f"Approval note: {rationale}"
    if approve and d.scenario_id:
        scenario = db.get(Scenario, d.scenario_id)
        if scenario:
            scenario.status = "adopted"
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type="user", actor_id=actor_id,
                 action=f"decision.{d.status}", entity_type="decision", entity_id=d.id)
    return d
