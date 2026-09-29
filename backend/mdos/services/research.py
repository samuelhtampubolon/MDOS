"""Research design adoption, rollback and workflow progress."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import audit
from ..models import (
    Analysis,
    Construct,
    Dataset,
    DatasetVersion,
    Decision,
    Evidence,
    Hypothesis,
    Insight,
    Project,
    Question,
    Recommendation,
    Report,
    ResearchPlan,
    ResearchQuestion,
    Survey,
    Variable,
)
from ..research.constructs import LIBRARY

DEMOGRAPHIC_CODES = {"origin", "home_region", "age_group", "gender", "income_level", "visits_before", "travel_party",
                     "discovery_channel", "nights_planned", "spend_per_day_idr", "recommend_0_10"}
PLAN_KINDS = ("framing", "design", "sampling", "fieldwork", "interview_guide", "qa")


def _role_for_construct(code: str, hypotheses: list[dict[str, Any]]) -> str:
    if any(h.get("mediator") == code for h in hypotheses):
        return "mediator"
    if any(h.get("moderator") == code for h in hypotheses):
        return "moderator"
    if any(h.get("dv") == code for h in hypotheses):
        return "dv"
    return "iv"


def _question_var(q: dict[str, Any]) -> tuple[str, str, float | None, float | None, dict]:
    """Map a questionnaire item to (var_type, role, scale_min, scale_max, value_labels)."""
    code, qtype = q["code"], q["qtype"]
    scale = q.get("scale") or {}
    if code == "attention_check":
        return "likert", "screening", 1, 5, {"expected": scale.get("expected", 4)}
    if code.startswith("screen_"):
        return "binary", "screening", None, None, {}
    if code.startswith(("wtp_", "gg_")):
        return "binary", "price", None, None, {"positive": "Ya"}
    if code.startswith("vw_"):
        return "price", "price", None, None, {}
    if qtype == "likert":
        return "likert", "other", float(scale.get("min", 1)), float(scale.get("max", 5)), {}
    if qtype == "text":
        return "text", "text", None, None, {}
    if qtype == "price":
        return "price", "descriptor", None, None, {}
    if qtype == "numeric":
        return "numeric", "descriptor", scale.get("min"), scale.get("max"), {}
    if qtype in ("single", "multi"):
        options = {str(o["value"]): o.get("label", o["value"]) for o in q.get("options", [])}
        return ("binary" if len(options) == 2 else "categorical"), "descriptor", None, None, options
    return "other", "other", None, None, {}


def adopt_design(db: Session, project: Project, package: dict[str, Any], run_id: str, user_id: str) -> dict[str, int]:
    """Create research entities from an approved design package. Every row is tagged with the run ID."""
    design = package.get("design") or {}
    hypotheses = design.get("hypotheses") or []
    counts = {"research_questions": 0, "hypotheses": 0, "constructs": 0, "variables": 0, "questions": 0, "plans": 0}

    existing_rq = db.scalar(select(func.count()).select_from(ResearchQuestion).where(ResearchQuestion.project_id == project.id)) or 0
    for i, text in enumerate(design.get("research_questions") or [], start=existing_rq + 1):
        db.add(ResearchQuestion(project_id=project.id, code=f"RQ{i}", text=text, source_run_id=run_id))
        counts["research_questions"] += 1

    existing_codes = set(db.scalars(select(Hypothesis.code).where(Hypothesis.project_id == project.id)).all())
    offset = len(existing_codes)
    for i, h in enumerate(hypotheses, start=1):
        code = h["code"] if h["code"] not in existing_codes else f"H{offset + i}"
        db.add(Hypothesis(project_id=project.id, code=code, statement=h["statement"], iv=h.get("iv", ""), dv=h.get("dv", ""),
                          mediator=h.get("mediator", ""), moderator=h.get("moderator", ""),
                          expected_direction=h.get("expected_direction", "positive"), rationale=h.get("rationale", ""),
                          source_run_id=run_id))
        counts["hypotheses"] += 1

    existing_constructs = {c.code: c for c in db.scalars(select(Construct).where(Construct.project_id == project.id)).all()}
    existing_vars = set(db.scalars(select(Variable.name).where(Variable.project_id == project.id)).all())
    construct_ids: dict[str, str] = {}
    for c in design.get("constructs") or []:
        if c["code"] in existing_constructs:
            construct_ids[c["code"]] = existing_constructs[c["code"]].id
            continue
        row = Construct(project_id=project.id, code=c["code"], name=c["name"], definition=c.get("definition", ""),
                        library_key=c.get("key", ""), source_reference=c.get("source", ""), source_run_id=run_id)
        db.add(row)
        db.flush()
        construct_ids[c["code"]] = row.id
        counts["constructs"] += 1
        if c["code"] not in existing_vars:
            db.add(Variable(project_id=project.id, construct_id=row.id, name=c["code"], label=f"{c['name']} (mean score)",
                            var_type="numeric", role=_role_for_construct(c["code"], hypotheses), scale_min=1, scale_max=5,
                            source_run_id=run_id))
            existing_vars.add(c["code"])
            counts["variables"] += 1

    survey_pkg = package.get("questionnaire") or {}
    if survey_pkg.get("questions"):
        survey = Survey(project_id=project.id, title=survey_pkg.get("title", "Survey"), introduction=survey_pkg.get("introduction", ""),
                        consent_text=survey_pkg.get("consent_text", ""), languages=survey_pkg.get("languages", ["en", "id"]),
                        source_run_id=run_id)
        db.add(survey)
        db.flush()
        for q in survey_pkg["questions"]:
            db.add(Question(survey_id=survey.id, project_id=project.id, code=q["code"], section=q.get("section", ""),
                            position=q.get("position", 0), qtype=q["qtype"], text=q["text"], text_id=q.get("text_id", ""),
                            options=q.get("options", []), scale=q.get("scale", {}), logic=q.get("logic", {}),
                            required=q.get("required", True), construct_code=q.get("construct_code", ""), source_run_id=run_id))
            counts["questions"] += 1
            if q["qtype"] == "info" or q["code"] in existing_vars:
                continue
            var_type, role, lo, hi, values = _question_var(q)
            construct_code = q.get("construct_code") or ""
            if construct_code:
                role = _role_for_construct(construct_code, hypotheses)
            db.add(Variable(project_id=project.id, construct_id=construct_ids.get(construct_code), name=q["code"],
                            label=q["text"][:500], var_type=var_type, role=role, scale_min=lo, scale_max=hi,
                            value_labels=values, source_run_id=run_id))
            existing_vars.add(q["code"])
            counts["variables"] += 1

    plans = {"framing": package.get("framing"), "design": {k: v for k, v in design.items() if k not in ("constructs",)},
             "sampling": package.get("sampling"), "fieldwork": package.get("fieldwork"),
             "interview_guide": {"questions": survey_pkg.get("interview_guide", [])} if survey_pkg.get("interview_guide") else None,
             "qa": package.get("qa")}
    for kind, content in plans.items():
        if not content:
            continue
        db.execute(delete(ResearchPlan).where(ResearchPlan.project_id == project.id, ResearchPlan.kind == kind))
        db.add(ResearchPlan(project_id=project.id, kind=kind, content=content, source_run_id=run_id))
        counts["plans"] += 1

    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type="user", actor_id=user_id,
                 action="research.design.adopt", entity_type="agent_run", entity_id=run_id, details=counts)
    return counts


def rollback_design(db: Session, project: Project, run_id: str, user_id: str) -> dict[str, int]:
    """Delete rows created by adopting ``run_id``, unless a person has decided on them since."""
    decided = db.scalar(select(func.count()).select_from(Hypothesis).where(
        Hypothesis.source_run_id == run_id, Hypothesis.decided_by.is_not(None)))
    if decided:
        from ..errors import Conflict

        raise Conflict("Some hypotheses from this design already have approved verdicts; roll back is blocked.")
    counts = {}
    for model in (Question, Survey, Variable, Construct, Hypothesis, ResearchQuestion, ResearchPlan):
        result = db.execute(delete(model).where(model.project_id == project.id, model.source_run_id == run_id))
        counts[model.__tablename__] = result.rowcount or 0
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type="user", actor_id=user_id,
                 action="research.design.rollback", entity_type="agent_run", entity_id=run_id, details=counts)
    return counts


def progress(db: Session, project: Project) -> list[dict[str, Any]]:
    """Status of the 23 research workflow steps named in the specification."""
    pid = project.id

    def count(model, *where) -> int:
        return int(db.scalar(select(func.count()).select_from(model).where(model.project_id == pid, *where)) or 0)

    plans = set(db.scalars(select(ResearchPlan.kind).where(ResearchPlan.project_id == pid)).all())
    methods = set(db.scalars(select(Analysis.method).where(Analysis.project_id == pid)).all())
    surveys = db.scalars(select(Survey).where(Survey.project_id == pid)).all()
    cleaned = count(DatasetVersion, DatasetVersion.version > 1)
    datasets = count(Dataset)
    profiled = any(v.get("issues") is not None for v in db.scalars(
        select(DatasetVersion.quality).where(DatasetVersion.project_id == pid)).all() if isinstance(v, dict))
    verdicts = count(Hypothesis, Hypothesis.status.in_(("supported", "not_supported", "inconclusive")))
    steps = [
        ("Problem definition", bool(project.business_question)),
        ("Research objective", "framing" in plans),
        ("Research questions", count(ResearchQuestion) > 0),
        ("Hypotheses", count(Hypothesis) > 0),
        ("Conceptual framework", "design" in plans),
        ("Variable design", count(Variable) > 0),
        ("Measurement model", count(Construct) > 0),
        ("Sampling plan", "sampling" in plans),
        ("Instrument design", any(s.questions for s in surveys)),
        ("Pilot review", any(s.status in ("approved", "fielded", "closed") for s in surveys)),
        ("Fieldwork", "fieldwork" in plans and datasets > 0),
        ("Data ingestion", datasets > 0),
        ("Data quality", profiled),
        ("Data cleaning", cleaned > 0),
        ("Exploratory analysis", "descriptive" in methods),
        ("Statistical analysis", bool(methods & {"regression_ols", "regression_logistic", "mediation", "moderation",
                                                  "correlation", "crosstab", "reliability"})),
        ("Segmentation", "segmentation" in methods),
        ("Synthesis", count(Evidence) > 0),
        ("Insight generation", count(Insight) > 0),
        ("Recommendation generation", count(Recommendation) > 0),
        ("Report generation", count(Report) > 0),
        ("Presentation generation", None),
        ("Decision tracking", count(Decision) > 0 or verdicts > 0),
    ]
    return [{"step": i + 1, "name": name, "status": "deferred" if done is None else ("done" if done else "todo")}
            for i, (name, done) in enumerate(steps)]


def library_construct(key: str) -> dict[str, Any] | None:
    c = LIBRARY.get(key)
    return c.as_dict() if c else None
