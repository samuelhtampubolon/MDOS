"""Research design entities: research questions, hypotheses, constructs, variables, plans and surveys."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import ProjectAccess, project_access
from ..errors import NotFound, ValidationFailed
from ..models import Construct, Hypothesis, Question, ResearchPlan, ResearchQuestion, Survey, Variable
from ..research import questionnaire as qexport
from ..research.language import causal_terms
from ..services import approvals
from ..services import evidence as evidence_service
from ..services import research as research_service
from .common import get_owned, next_code, to_dict

router = APIRouter(prefix="/projects/{project_id}", tags=["research"])


class RQIn(BaseModel):
    text: str = Field(min_length=5, max_length=2000)


class HypothesisIn(BaseModel):
    statement: str = Field(min_length=5, max_length=2000)
    iv: str = ""
    dv: str = ""
    mediator: str = ""
    moderator: str = ""
    expected_direction: Literal["positive", "negative", "difference", "none"] = "positive"
    rationale: str = ""


class ConstructIn(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    definition: str = ""
    library_key: str = ""
    source_reference: str = ""


class VariableIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    label: str = ""
    var_type: Literal["likert", "numeric", "categorical", "binary", "text", "price", "id", "datetime"] = "numeric"
    role: Literal["iv", "dv", "mediator", "moderator", "control", "descriptor", "screening", "text", "price", "other"] = "other"
    construct_id: str | None = None
    scale_min: float | None = None
    scale_max: float | None = None
    value_labels: dict = Field(default_factory=dict)


class VariablePatch(BaseModel):
    label: str | None = None
    var_type: Literal["likert", "numeric", "categorical", "binary", "text", "price", "id", "datetime"] | None = None
    role: Literal["iv", "dv", "mediator", "moderator", "control", "descriptor", "screening", "text", "price", "other"] | None = None
    construct_id: str | None = None
    scale_min: float | None = None
    scale_max: float | None = None
    value_labels: dict | None = None


class PlanIn(BaseModel):
    content: dict


class SurveyPatch(BaseModel):
    title: str | None = None
    introduction: str | None = None
    consent_text: str | None = None
    status: Literal["draft", "approved", "fielded", "closed"] | None = None


class QuestionIn(BaseModel):
    code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    section: str = ""
    qtype: Literal["single", "multi", "likert", "numeric", "text", "price", "info"]
    text: str = Field(min_length=1, max_length=2000)
    text_id: str = ""
    options: list[dict] = Field(default_factory=list)
    scale: dict = Field(default_factory=dict)
    logic: dict = Field(default_factory=dict)
    required: bool = True
    construct_code: str = ""
    position: int | None = None


class QuestionPatch(BaseModel):
    section: str | None = None
    text: str | None = None
    text_id: str | None = None
    options: list[dict] | None = None
    scale: dict | None = None
    logic: dict | None = None
    required: bool | None = None
    position: int | None = None


class VerdictIn(BaseModel):
    verdict: Literal["supported", "not_supported", "inconclusive"]
    evidence_ids: list[str] = Field(min_length=1)
    rationale: str = ""


class VerdictDecisionIn(BaseModel):
    approve: bool
    rationale: str = ""
    verdict: Literal["supported", "not_supported", "inconclusive"] | None = None


def _audit(db: Session, access: ProjectAccess, action: str, entity_type: str, entity_id: str, details: dict | None = None) -> None:
    audit.record(db, org_id=access.user.org_id, project_id=access.project.id, actor_type="user", actor_id=access.actor,
                 action=action, entity_type=entity_type, entity_id=entity_id, details=details)


def _survey_out(survey: Survey) -> dict:
    data = to_dict(survey)
    data["questions"] = [to_dict(q) for q in survey.questions]
    return data


@router.get("/research")
def overview(access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    pid = access.project.id
    surveys = db.scalars(select(Survey).where(Survey.project_id == pid).order_by(Survey.created_at)).all()
    return {
        "research_questions": [to_dict(r) for r in db.scalars(select(ResearchQuestion).where(ResearchQuestion.project_id == pid)
                                                              .order_by(ResearchQuestion.code)).all()],
        "hypotheses": [to_dict(h) for h in db.scalars(select(Hypothesis).where(Hypothesis.project_id == pid)
                                                      .order_by(Hypothesis.code)).all()],
        "constructs": [to_dict(c) for c in db.scalars(select(Construct).where(Construct.project_id == pid)
                                                      .order_by(Construct.code)).all()],
        "variables": [to_dict(v) for v in db.scalars(select(Variable).where(Variable.project_id == pid)
                                                     .order_by(Variable.name)).all()],
        "plans": {p.kind: to_dict(p) for p in db.scalars(select(ResearchPlan).where(ResearchPlan.project_id == pid)).all()},
        "surveys": [{**to_dict(s), "question_count": len(s.questions)} for s in surveys],
        "progress": research_service.progress(db, access.project),
    }


@router.get("/research/progress")
def progress(access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> list[dict]:
    return research_service.progress(db, access.project)


# ---- research questions ------------------------------------------------------------------------


@router.post("/research-questions", status_code=201)
def create_rq(body: RQIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    rq = ResearchQuestion(project_id=access.project.id, code=next_code(db, ResearchQuestion, access.project.id, "RQ"), text=body.text)
    db.add(rq)
    db.flush()
    _audit(db, access, "research_question.create", "research_question", rq.id)
    db.commit()
    return to_dict(rq)


@router.patch("/research-questions/{rq_id}")
def update_rq(rq_id: str, body: RQIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    rq = get_owned(db, ResearchQuestion, rq_id, access.project.id)
    rq.text = body.text
    _audit(db, access, "research_question.update", "research_question", rq.id)
    db.commit()
    return to_dict(rq)


@router.delete("/research-questions/{rq_id}", status_code=204)
def delete_rq(rq_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> None:
    access.require("editor")
    rq = get_owned(db, ResearchQuestion, rq_id, access.project.id)
    db.delete(rq)
    _audit(db, access, "research_question.delete", "research_question", rq_id)
    db.commit()


# ---- hypotheses --------------------------------------------------------------------------------


@router.post("/hypotheses", status_code=201)
def create_hypothesis(body: HypothesisIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    h = Hypothesis(project_id=access.project.id, code=next_code(db, Hypothesis, access.project.id, "H"), **body.model_dump())
    db.add(h)
    db.flush()
    _audit(db, access, "hypothesis.create", "hypothesis", h.id)
    db.commit()
    out = to_dict(h)
    out["causal_terms"] = causal_terms(body.statement)
    return out


@router.patch("/hypotheses/{hypothesis_id}")
def update_hypothesis(hypothesis_id: str, body: HypothesisIn, access: ProjectAccess = Depends(project_access),
                      db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    h = get_owned(db, Hypothesis, hypothesis_id, access.project.id)
    if h.decided_by:
        raise ValidationFailed("This hypothesis has an approved verdict; create a new hypothesis instead of editing it.")
    for key, value in body.model_dump().items():
        setattr(h, key, value)
    _audit(db, access, "hypothesis.update", "hypothesis", h.id)
    db.commit()
    return to_dict(h)


@router.delete("/hypotheses/{hypothesis_id}", status_code=204)
def delete_hypothesis(hypothesis_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> None:
    access.require("editor")
    h = get_owned(db, Hypothesis, hypothesis_id, access.project.id)
    db.delete(h)
    _audit(db, access, "hypothesis.delete", "hypothesis", hypothesis_id)
    db.commit()


@router.post("/hypotheses/{hypothesis_id}/verdict")
def propose_verdict(hypothesis_id: str, body: VerdictIn, access: ProjectAccess = Depends(project_access),
                    db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    h = get_owned(db, Hypothesis, hypothesis_id, access.project.id)
    evidence_service.propose_verdict(db, access.project, h, body.verdict, body.evidence_ids, body.rationale, actor_id=access.actor)
    approvals.request(db, access.project, action="approve_verdict", entity_type="hypothesis", entity_id=h.id,
                      summary=f"{h.code}: proposed {body.verdict.replace('_', ' ')}", requested_by=access.actor)
    db.commit()
    return to_dict(h)


@router.post("/hypotheses/{hypothesis_id}/verdict/decide")
def decide_verdict(hypothesis_id: str, body: VerdictDecisionIn, access: ProjectAccess = Depends(project_access),
                   db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    h = get_owned(db, Hypothesis, hypothesis_id, access.project.id)
    evidence_service.decide_verdict(db, access.project, h, body.approve, access.actor, body.rationale, body.verdict)
    approvals.resolve_pending(db, access.project, "approve_verdict", h.id, "approved" if body.approve else "rejected",
                              access.actor, body.rationale)
    db.commit()
    return to_dict(h)


# ---- constructs and variables ------------------------------------------------------------------


@router.post("/constructs", status_code=201)
def create_construct(body: ConstructIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    if db.scalar(select(Construct).where(Construct.project_id == access.project.id, Construct.code == body.code)):
        raise ValidationFailed(f"Construct code '{body.code}' already exists.")
    c = Construct(project_id=access.project.id, **body.model_dump())
    db.add(c)
    db.flush()
    _audit(db, access, "construct.create", "construct", c.id)
    db.commit()
    return to_dict(c)


@router.delete("/constructs/{construct_id}", status_code=204)
def delete_construct(construct_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> None:
    access.require("editor")
    c = get_owned(db, Construct, construct_id, access.project.id)
    db.delete(c)
    _audit(db, access, "construct.delete", "construct", construct_id)
    db.commit()


@router.post("/variables", status_code=201)
def create_variable(body: VariableIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    if db.scalar(select(Variable).where(Variable.project_id == access.project.id, Variable.name == body.name)):
        raise ValidationFailed(f"Variable '{body.name}' already exists.")
    if body.construct_id:
        get_owned(db, Construct, body.construct_id, access.project.id)
    v = Variable(project_id=access.project.id, **body.model_dump())
    db.add(v)
    db.flush()
    _audit(db, access, "variable.create", "variable", v.id)
    db.commit()
    return to_dict(v)


@router.patch("/variables/{variable_id}")
def update_variable(variable_id: str, body: VariablePatch, access: ProjectAccess = Depends(project_access),
                    db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    v = get_owned(db, Variable, variable_id, access.project.id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("construct_id"):
        get_owned(db, Construct, changes["construct_id"], access.project.id)
    for key, value in changes.items():
        setattr(v, key, value)
    _audit(db, access, "variable.update", "variable", v.id, {"fields": sorted(changes)})
    db.commit()
    return to_dict(v)


@router.delete("/variables/{variable_id}", status_code=204)
def delete_variable(variable_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> None:
    access.require("editor")
    v = get_owned(db, Variable, variable_id, access.project.id)
    db.delete(v)
    _audit(db, access, "variable.delete", "variable", variable_id)
    db.commit()


# ---- plans -------------------------------------------------------------------------------------


@router.put("/plans/{kind}")
def put_plan(kind: str, body: PlanIn, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    if kind not in research_service.PLAN_KINDS:
        raise ValidationFailed(f"Plan kind must be one of {', '.join(research_service.PLAN_KINDS)}.")
    db.execute(delete(ResearchPlan).where(ResearchPlan.project_id == access.project.id, ResearchPlan.kind == kind))
    plan = ResearchPlan(project_id=access.project.id, kind=kind, content=body.content)
    db.add(plan)
    db.flush()
    _audit(db, access, "plan.update", "research_plan", plan.id, {"kind": kind})
    db.commit()
    return to_dict(plan)


# ---- surveys -----------------------------------------------------------------------------------


@router.get("/surveys/{survey_id}")
def get_survey(survey_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    return _survey_out(get_owned(db, Survey, survey_id, access.project.id))


@router.patch("/surveys/{survey_id}")
def update_survey(survey_id: str, body: SurveyPatch, access: ProjectAccess = Depends(project_access),
                  db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    survey = get_owned(db, Survey, survey_id, access.project.id)
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(survey, key, value)
    if "status" in changes and changes["status"] == "approved":
        survey.version += 1
    _audit(db, access, "survey.update", "survey", survey.id, {"fields": sorted(changes)})
    db.commit()
    return _survey_out(survey)


@router.post("/surveys/{survey_id}/questions", status_code=201)
def add_question(survey_id: str, body: QuestionIn, access: ProjectAccess = Depends(project_access),
                 db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    survey = get_owned(db, Survey, survey_id, access.project.id)
    if any(q.code == body.code for q in survey.questions):
        raise ValidationFailed(f"Question code '{body.code}' already exists in this survey.")
    data = body.model_dump()
    if data["position"] is None:
        data["position"] = max((q.position for q in survey.questions), default=-1) + 1
    q = Question(survey_id=survey.id, project_id=access.project.id, **data)
    db.add(q)
    db.flush()
    _audit(db, access, "question.create", "question", q.id)
    db.commit()
    return to_dict(q)


@router.patch("/surveys/{survey_id}/questions/{question_id}")
def update_question(survey_id: str, question_id: str, body: QuestionPatch, access: ProjectAccess = Depends(project_access),
                    db: Session = Depends(get_db)) -> dict:
    access.require("editor")
    get_owned(db, Survey, survey_id, access.project.id)
    q = get_owned(db, Question, question_id, access.project.id)
    if q.survey_id != survey_id:
        raise NotFound("Question not found.")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(q, key, value)
    _audit(db, access, "question.update", "question", q.id)
    db.commit()
    return to_dict(q)


@router.delete("/surveys/{survey_id}/questions/{question_id}", status_code=204)
def delete_question(survey_id: str, question_id: str, access: ProjectAccess = Depends(project_access),
                    db: Session = Depends(get_db)) -> None:
    access.require("editor")
    q = get_owned(db, Question, question_id, access.project.id)
    if q.survey_id != survey_id:
        raise NotFound("Question not found.")
    db.delete(q)
    _audit(db, access, "question.delete", "question", question_id)
    db.commit()


@router.get("/surveys/{survey_id}/export")
def export_survey(survey_id: str, format: Literal["xlsform", "markdown", "codebook", "json"] = "xlsform",
                  access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> Response:
    survey = get_owned(db, Survey, survey_id, access.project.id)
    data = _survey_out(survey)
    questions = data["questions"]
    slug = "".join(ch if ch.isalnum() else "_" for ch in survey.title.lower())[:40] or "survey"
    if format == "xlsform":
        return Response(qexport.to_xlsform(data, questions),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="{slug}_xlsform.xlsx"'})
    if format == "markdown":
        return Response(qexport.to_markdown(data, questions), media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{slug}.md"'})
    if format == "codebook":
        variables = {v.name: to_dict(v) for v in db.scalars(select(Variable).where(Variable.project_id == access.project.id)).all()}
        return Response(qexport.to_codebook_csv(questions, variables), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{slug}_codebook.csv"'})
    import json

    return Response(json.dumps(data, indent=2, default=str), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{slug}.json"'})
