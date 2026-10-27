"""Tools that agents may call. Agents reach them only through ``AgentContext.tool(name)``, which enforces
each agent's allowlist. No tool deletes data; destructive changes go through approvals."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select

from ..analytics import cleaning, power
from ..models import Construct, Dataset, Evidence, Hypothesis, Journey, ResearchPlan, Scenario, Variable
from ..research import constructs
from ..research.design import generate_all
from ..services import analyses as analysis_service
from ..services import approvals
from ..services import datasets as dataset_service
from ..services import evidence as evidence_service
from ..services import journey as journey_service
from ..services import reports as report_service
from ..services import strategy as strategy_service
from .contract import AgentBlocked, AgentContext

TOOLS: dict[str, Callable[..., Any]] = {}


def tool(name: str):
    def register(fn: Callable[..., Any]) -> Callable[..., Any]:
        TOOLS[name] = fn
        return fn

    return register


def _actor(ctx: AgentContext, agent: str | None = None) -> str:
    return f"agent:{agent or ctx.state.get('_agent', 'agent')}"


# ---- project and knowledge ------------------------------------------------------------------------


@tool("project.read")
def project_read(ctx: AgentContext) -> dict[str, Any]:
    p = ctx.project
    ctx.used("project.business_question")
    db = ctx.db
    return {
        "id": p.id, "name": p.name, "business_question": p.business_question, "decision_to_inform": p.decision_to_inform,
        "context": p.context, "industry": p.industry, "geography": p.geography, "currency": p.currency,
        "plans": {r.kind: r.content for r in db.scalars(select(ResearchPlan).where(ResearchPlan.project_id == p.id)).all()},
        "hypotheses": db.scalars(select(Hypothesis).where(Hypothesis.project_id == p.id).order_by(Hypothesis.code)).all(),
        "constructs": db.scalars(select(Construct).where(Construct.project_id == p.id)).all(),
        "variables": {v.name: v for v in db.scalars(select(Variable).where(Variable.project_id == p.id)).all()},
    }


@tool("construct_library.search")
def construct_search(ctx: AgentContext, query: str = "", tags: list[str] | None = None) -> list[dict]:
    ctx.used("construct_library")
    return constructs.search(query, tags)


@tool("design.generate")
def design_generate(ctx: AgentContext) -> dict[str, Any]:
    p = ctx.project
    return generate_all({"name": p.name, "business_question": p.business_question, "decision_to_inform": p.decision_to_inform,
                         "industry": p.industry, "currency": p.currency})


@tool("calc.sample_size")
def sample_size(ctx: AgentContext, **kwargs: Any) -> dict[str, Any]:
    return power.sample_size_proportion(**kwargs)


@tool("llm.generate")
def llm_generate(ctx: AgentContext, *, system: str, prompt: str, schema: type[BaseModel], max_tokens: int = 16000):
    result = ctx.provider.generate(system=system, prompt=prompt, schema=schema, max_tokens=max_tokens)
    ctx.llm_calls.append({**result.meta, "schema": schema.__name__, "error": result.error})
    if result.error and result.error != "offline":
        ctx.uncertainties.append(f"Claude drafting was unavailable ({result.error}); the deterministic draft was used.")
    return result.parsed


# ---- data and analysis ------------------------------------------------------------------------------


@tool("dataset.read")
def dataset_read(ctx: AgentContext, dataset_id: str | None = None, kind: str = "survey"):
    db = ctx.db
    if dataset_id:
        dataset = db.get(Dataset, dataset_id)
        if not dataset or dataset.project_id != ctx.project.id:
            raise AgentBlocked("The selected dataset was not found in this project.")
    else:
        dataset = db.scalars(select(Dataset).where(Dataset.project_id == ctx.project.id, Dataset.kind == kind)
                             .order_by(Dataset.created_at)).first()
        if not dataset:
            raise AgentBlocked(f"Upload a {kind} dataset first.")
    version = dataset_service.current_version(db, dataset)
    ctx.used(f"dataset:{dataset.name} v{version.version}")
    return dataset, version


@tool("dataset.load")
def dataset_load(ctx: AgentContext, version):
    return dataset_service.load_version(version)


@tool("dataset.profile")
def dataset_profile(ctx: AgentContext, version) -> dict[str, Any]:
    return version.quality or {}


@tool("cleaning.propose")
def cleaning_propose(ctx: AgentContext, quality: dict[str, Any]) -> list[dict[str, Any]]:
    return cleaning.propose_plan(quality)


@tool("dataset.derive_scores")
def derive_scores(ctx: AgentContext, version):
    """Non-destructive: adds construct mean scores as a new version (lineage recorded)."""
    ops = dataset_service.construct_scale_operations(ctx.db, ctx.project.id, [c["name"] for c in version.columns])
    if not ops:
        return version
    return dataset_service.derive_version(ctx.db, ctx.project, version, ops, user_id=_actor(ctx), approved_by=None,
                                          source_run_id=ctx.source_run_id)


@tool("analysis.run")
def analysis_run(ctx: AgentContext, version, method: str, params: dict[str, Any], title: str = ""):
    analysis = analysis_service.run_analysis(ctx.db, ctx.project, version, method, params, actor_id=_actor(ctx),
                                             actor_type="agent", source_run_id=ctx.source_run_id, title=title)
    ctx.act(f"Ran {method}: {analysis.result.get('summary', '')[:160]}")
    return analysis


@tool("evidence.create")
def evidence_create(ctx: AgentContext, analysis, keys: list[str] | None = None) -> list[Evidence]:
    rows = analysis_service.evidence_from_analysis(ctx.db, ctx.project, analysis, keys, actor_id=_actor(ctx),
                                                   actor_type="agent", source_run_id=ctx.source_run_id)
    ctx.cite(*[e.code for e in rows])
    return rows


@tool("evidence.read")
def evidence_read(ctx: AgentContext) -> list[Evidence]:
    ctx.used("evidence register")
    return ctx.db.scalars(select(Evidence).where(Evidence.project_id == ctx.project.id).order_by(Evidence.seq)).all()


@tool("insight.propose")
def insight_propose(ctx: AgentContext, **kwargs: Any):
    insight = evidence_service.create_insight(ctx.db, ctx.project, actor_id=_actor(ctx), actor_type="agent",
                                              source_run_id=ctx.source_run_id, **kwargs)
    approvals.request(ctx.db, ctx.project, action="approve_insight", entity_type="insight", entity_id=insight.id,
                      summary=f"{insight.code}: {insight.title}", requested_by=_actor(ctx))
    return insight


@tool("verdict.propose")
def verdict_propose(ctx: AgentContext, hypothesis, verdict: str, evidence_ids: list[str], rationale: str):
    evidence_service.propose_verdict(ctx.db, ctx.project, hypothesis, verdict, evidence_ids, rationale, actor_id=_actor(ctx),
                                     actor_type="agent")
    approvals.request(ctx.db, ctx.project, action="approve_verdict", entity_type="hypothesis", entity_id=hypothesis.id,
                      summary=f"{hypothesis.code}: proposed {verdict.replace('_', ' ')}", requested_by=_actor(ctx))
    return hypothesis


@tool("recommendation.propose")
def recommendation_propose(ctx: AgentContext, **kwargs: Any):
    rec = evidence_service.create_recommendation(ctx.db, ctx.project, actor_id=_actor(ctx), actor_type="agent",
                                                 source_run_id=ctx.source_run_id, **kwargs)
    approvals.request(ctx.db, ctx.project, action="approve_recommendation", entity_type="recommendation", entity_id=rec.id,
                      summary=f"{rec.code}: {rec.statement[:120]}", requested_by=_actor(ctx))
    return rec


@tool("report.compose")
def report_compose(ctx: AgentContext, kind: str = "research_report"):
    report = report_service.generate(ctx.db, ctx.project, kind, actor_id=_actor(ctx), actor_type="agent",
                                     source_run_id=ctx.source_run_id)
    approvals.request(ctx.db, ctx.project, action="finalize_report", entity_type="report", entity_id=report.id,
                      summary=f"Finalize {report.title}", requested_by=_actor(ctx))
    return report


# ---- strategy ---------------------------------------------------------------------------------------


@tool("scenario.read")
def scenario_read(ctx: AgentContext) -> list[Scenario]:
    return ctx.db.scalars(select(Scenario).where(Scenario.project_id == ctx.project.id).order_by(Scenario.created_at)).all()


@tool("scenario.propose")
def scenario_propose(ctx: AgentContext, action: str, **kwargs: Any):
    db, project = ctx.db, ctx.project
    if action == "baseline":
        model, inputs = strategy_service.build_default_model(db, project)
        baseline = strategy_service.create_baseline(db, project, model, name=kwargs.get("name", "Baseline (evidence-based)"),
                                                    actor_id=_actor(ctx), actor_type="agent", source_run_id=ctx.source_run_id)
        return baseline, inputs
    if action == "what_ifs":
        return strategy_service.graph1_what_ifs(db, project, kwargs["baseline"], actor_id=_actor(ctx), actor_type="agent",
                                                source_run_id=ctx.source_run_id)
    if action == "scenario":
        return strategy_service.create_scenario(db, project, kwargs["baseline"], name=kwargs["name"], levers=kwargs["levers"],
                                                description=kwargs.get("description", ""), actor_id=_actor(ctx),
                                                actor_type="agent", source_run_id=ctx.source_run_id)
    raise ValueError(f"Unknown scenario action '{action}'.")


@tool("scenario.simulate")
def scenario_simulate(ctx: AgentContext, analysis_name: str, scenario: Scenario, **kwargs: Any):
    from ..strategy import analysis as strat

    model = strategy_service.validate_model(scenario.model)
    fn = {"sensitivity": strat.sensitivity, "monte_carlo": strat.monte_carlo, "price_curve": strat.price_curve,
          "optimize_media": strat.optimize_media}[analysis_name]
    return fn(model, **kwargs)


@tool("decision.propose")
def decision_propose(ctx: AgentContext, **kwargs: Any):
    d = strategy_service.create_decision(ctx.db, ctx.project, actor_id=_actor(ctx), actor_type="agent", **kwargs)
    approvals.request(ctx.db, ctx.project, action="approve_decision", entity_type="decision", entity_id=d.id,
                      summary=f"Decision: {d.title}", requested_by=_actor(ctx))
    return d


# ---- journey ----------------------------------------------------------------------------------------


@tool("journey.read")
def journey_read(ctx: AgentContext, journey_id: str | None = None) -> Journey | None:
    if journey_id:
        return journey_service.get_journey(ctx.db, ctx.project.id, journey_id)
    return ctx.db.scalars(select(Journey).where(Journey.project_id == ctx.project.id).order_by(Journey.created_at.desc())).first()


@tool("journey.propose")
def journey_propose(ctx: AgentContext, action: str, **kwargs: Any):
    if action == "create":
        return journey_service.create_journey(ctx.db, ctx.project, name=kwargs.get("name", "Customer journey"),
                                              template_key=kwargs.get("template", "tourism"), actor_id=_actor(ctx),
                                              actor_type="agent", source_run_id=ctx.source_run_id)
    if action == "apply_voc":
        journey_service.apply_voc(ctx.db, ctx.project, kwargs["journey"], kwargs["analysis"], kwargs["evidence"],
                                  source_run_id=ctx.source_run_id)
        return kwargs["journey"]
    if action == "interventions":
        return journey_service.propose_interventions(ctx.db, ctx.project, kwargs["journey"], source_run_id=ctx.source_run_id)
    raise ValueError(f"Unknown journey action '{action}'.")


@tool("voc.analyze")
def voc_analyze(ctx: AgentContext, version, text_column: str, template: str, rating_column: str | None = None):
    params = {"text_column": text_column, "template": template}
    if rating_column:
        params["rating_column"] = rating_column
    analysis = analysis_run(ctx, version, "journey_voc", params)
    evidence = evidence_create(ctx, analysis)
    return analysis, evidence


@tool("journey.simulate")
def journey_simulate(ctx: AgentContext, journey: Journey, intervention):
    return journey_service.simulate_intervention(journey, intervention)


@tool("experiment.propose")
def experiment_propose(ctx: AgentContext, journey: Journey, intervention):
    exp = journey_service.experiment_from_intervention(ctx.db, ctx.project, journey, intervention, actor_id=_actor(ctx),
                                                       actor_type="agent", source_run_id=ctx.source_run_id)
    approvals.request(ctx.db, ctx.project, action="launch_experiment", entity_type="experiment", entity_id=exp.id,
                      summary=f"Launch experiment: {exp.name}", requested_by=_actor(ctx))
    return exp
