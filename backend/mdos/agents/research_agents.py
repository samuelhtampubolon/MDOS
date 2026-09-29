"""Research Lab agents (the Graph1 pipeline): framing, design, questionnaire, sampling, fieldwork, data quality,
cleaning, statistics, price sensitivity, segmentation, text, insights, QA and reporting."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from ..analytics.quality import detect_vw_columns
from ..research.language import causal_terms
from .base import Agent, register
from .contract import AgentBlocked, AgentContext, AgentResult
from .grounding import allowed_numbers, ungrounded_numbers, wrap_untrusted

DESIGN_TOOLS = frozenset({"project.read", "design.generate", "llm.generate"})


def _package(ctx: AgentContext) -> dict[str, Any]:
    if "package" not in ctx.state:
        ctx.state["package"] = ctx.tool("design.generate")() if "design.generate" in ctx.allowed_tools else {}
    return ctx.state["package"]


def ev_by_key(evidence) -> dict[str, Any]:
    return {(e.source_ref or {}).get("key"): e for e in evidence if (e.source_ref or {}).get("key")}


# ----------------------------------------------------------------------------------------------------
# Design pipeline
# ----------------------------------------------------------------------------------------------------


class FramingRefinement(BaseModel):
    decision_statement: str
    research_problem: str
    objectives: list[str] = Field(min_length=2, max_length=7)
    key_unknowns: list[str] = Field(min_length=1, max_length=6)


class DesignRefinement(BaseModel):
    research_questions: list[str] = Field(min_length=2, max_length=6)
    hypothesis_statements: list[str] = Field(description="One statement per hypothesis, same order and count as given")
    design_caveats: list[str] = Field(min_length=1, max_length=6)


class ConceptRefinement(BaseModel):
    concept_en: str = Field(description="Neutral 60-100 word description of the offer, no price")
    concept_id: str = Field(description="The same description in Bahasa Indonesia")


@register
class ResearchDirectorAgent(Agent):
    key = "research_director"
    name = "Research Director"
    module = "research"
    description = "Supervises research workflows: checks preconditions, plans the steps and summarizes the state."
    tools = frozenset({"project.read", "evidence.read"})
    covers = ("Research Director Agent",)

    def run(self, ctx: AgentContext) -> AgentResult:
        project = ctx.tool("project.read")()
        phase = ctx.state.get("phase", "design")
        ctx.used("research plans", "hypotheses")
        if phase == "analysis":
            if not project["hypotheses"]:
                raise AgentBlocked("Adopt a research design (hypotheses and constructs) before running the analysis workflow.")
            ctx.act(f"Confirmed {len(project['hypotheses'])} hypotheses and {len(project['constructs'])} constructs are in place.")
            plan = ["data_quality", "data_cleaning", "statistical_analysis", "price_sensitivity", "segmentation",
                    "text_analytics", "insight", "research_qa", "report"]
            next_step = "Review data-quality findings and approve the cleaning plan when asked."
        else:
            if project["hypotheses"]:
                ctx.uncertainties.append("This project already has hypotheses; adopting a new design adds to them.")
            plan = ["problem_framing", "research_design", "questionnaire", "sampling", "fieldwork", "research_qa"]
            next_step = "Review the generated design package, then approve its adoption."
        ctx.act(f"Planned the {phase} workflow: {', '.join(plan)}.")
        return ctx.result({"phase": phase, "plan": plan}, next_step)


@register
class ProblemFramingAgent(Agent):
    key = "problem_framing"
    name = "Problem Framing"
    module = "research"
    description = "Turns the business question into a decision statement, research problem, objectives and key unknowns."
    tools = DESIGN_TOOLS
    covers = ("Problem Framing Agent",)

    def run(self, ctx: AgentContext) -> AgentResult:
        project = ctx.tool("project.read")()
        package = _package(ctx)
        framing = dict(package["framing"])
        ctx.act("Parsed the business question: intents " + ", ".join(framing["intents"]) + ".")
        refined = ctx.tool("llm.generate")(
            system="You are the Problem Framing agent. Sharpen the framing without changing its meaning or scope.",
            prompt=(f"Business question: {wrap_untrusted(project['business_question'], 1500)}\n"
                    f"Decision to inform: {wrap_untrusted(project['decision_to_inform'] or 'not stated', 800)}\n"
                    f"Draft framing (JSON): {framing}\nReturn an improved version."),
            schema=FramingRefinement, max_tokens=4000)
        if refined is not None:
            text = " ".join([refined.decision_statement, refined.research_problem, *refined.objectives])
            if causal_terms(text):
                ctx.uncertainties.append("Model wording used causal language; kept the deterministic framing.")
            else:
                framing.update(refined.model_dump())
                framing["model_generated"] = True
                ctx.act("Refined wording of objectives with Claude.")
        ctx.assumptions.append("The study is descriptive and correlational; causal claims need a follow-up experiment.")
        package["framing"] = framing
        return ctx.result({"framing": framing}, "Review the objectives, then continue to research design.")


@register
class ResearchDesignAgent(Agent):
    key = "research_design"
    name = "Research Design"
    module = "research"
    description = "Research questions, hypotheses, constructs from the library, conceptual framework and analysis plan."
    tools = DESIGN_TOOLS | {"construct_library.search"}
    covers = ("Research Design Agent", "Hypothesis Agent", "Measurement Agent", "Literature Discovery Agent")

    def run(self, ctx: AgentContext) -> AgentResult:
        project = ctx.tool("project.read")()
        package = _package(ctx)
        design = dict(package["design"])
        library = ctx.tool("construct_library.search")()
        ctx.act(f"Selected {len(design['constructs'])} constructs from a library of {len(library)}: "
                + ", ".join(c["name"] for c in design["constructs"]) + ".")
        refined = ctx.tool("llm.generate")(
            system="You are the Research Design agent. Improve wording only. Keep hypotheses associational and testable.",
            prompt=(f"Business question: {wrap_untrusted(project['business_question'], 1500)}\n"
                    f"Research questions: {design['research_questions']}\n"
                    f"Hypotheses (keep order and count): {[h['statement'] for h in design['hypotheses']]}\n"
                    f"Caveats: {design['design_caveats']}"),
            schema=DesignRefinement, max_tokens=4000)
        if refined is not None:
            statements = refined.hypothesis_statements
            if len(statements) != len(design["hypotheses"]) or any(causal_terms(s) for s in statements):
                ctx.uncertainties.append("Model hypotheses changed count or used causal wording; kept deterministic hypotheses.")
            else:
                design["hypotheses"] = [{**h, "statement": s} for h, s in zip(design["hypotheses"], statements, strict=True)]
                design["research_questions"] = refined.research_questions
                design["design_caveats"] = refined.design_caveats
                design["model_generated"] = True
                ctx.act("Refined research questions and hypothesis wording with Claude.")
        for h in design["hypotheses"]:
            ctx.act(f"{h['code']}: {h['statement']} (test: {h['method']}).")
        ctx.assumptions += ["Adapted scale items need a comprehension pilot in both languages.",
                            "Construct items are adapted from cited sources; verify wording before academic use."]
        package["design"] = design
        return ctx.result({"design": design}, "Review hypotheses and constructs, then generate the questionnaire.")


@register
class QuestionnaireAgent(Agent):
    key = "questionnaire"
    name = "Questionnaire"
    module = "research"
    description = "Bilingual questionnaire with screening, construct items, attention check, price module and interview guide."
    tools = DESIGN_TOOLS | {"construct_library.search"}
    covers = ("Questionnaire Agent", "Interview Guide Agent")

    def run(self, ctx: AgentContext) -> AgentResult:
        project = ctx.tool("project.read")()
        package = _package(ctx)
        survey = dict(package["questionnaire"])
        questions = [dict(q) for q in survey["questions"]]
        refined = ctx.tool("llm.generate")(
            system="You are the Questionnaire agent. Write a neutral concept description that does not mention price.",
            prompt=(f"Business question: {wrap_untrusted(project['business_question'], 1500)}\n"
                    f"Context: {wrap_untrusted(project['context'] or 'none', 2000)}"),
            schema=ConceptRefinement, max_tokens=3000)
        if refined is not None and not re.search(r"\d", refined.concept_en + refined.concept_id):
            for q in questions:
                if q["code"] == "concept":
                    q["text"], q["text_id"] = refined.concept_en, refined.concept_id
            ctx.act("Drafted the concept description in English and Bahasa Indonesia with Claude.")
        else:
            ctx.uncertainties.append("The concept description is a placeholder; describe the offer before fieldwork.")
        survey["questions"] = questions
        price_q = [q["code"] for q in questions if q["code"].startswith(("wtp_", "vw_", "gg_"))]
        ctx.act(f"Built {len(questions)} items in {len({q['section'] for q in questions})} sections, including "
                f"{len(price_q)} price questions and an attention check.")
        ctx.assumptions.append("Indonesian wording is machine-drafted; a native speaker should review it.")
        package["questionnaire"] = survey
        return ctx.result({"questionnaire": {"title": survey["title"], "question_count": len(questions),
                                             "price_questions": price_q, "interview_guide": survey["interview_guide"]}},
                          "Export the XLSForm after adoption and pilot it with about 20 respondents.")


@register
class SamplingAgent(Agent):
    key = "sampling"
    name = "Sampling"
    module = "research"
    description = "Target population, sampling frame, method, sample size with margin of error and quotas."
    tools = frozenset({"project.read", "design.generate", "calc.sample_size"})
    covers = ("Sampling Agent",)

    def run(self, ctx: AgentContext) -> AgentResult:
        package = _package(ctx)
        sampling = package["sampling"]
        check = ctx.tool("calc.sample_size")(p=0.5, margin=0.05, confidence=0.95)
        ctx.act(f"Recommended n = {sampling['sample_size']['recommended']} (n = {check['n']} gives a 5% margin of error at 95%).")
        ctx.assumptions += sampling.get("assumptions", [])
        ctx.assumptions.append("Quota sampling is non-probability; results describe the sampled groups.")
        return ctx.result({"sampling": sampling}, "Confirm quotas with official visitor statistics if available.")


@register
class FieldworkAgent(Agent):
    key = "fieldwork"
    name = "Fieldwork"
    module = "research"
    description = "Fieldwork channels, timeline, quality control rules, consent and the XLSForm handoff."
    tools = frozenset({"project.read", "design.generate"})
    covers = ("Fieldwork Agent",)

    def run(self, ctx: AgentContext) -> AgentResult:
        package = _package(ctx)
        field = package["fieldwork"]
        ctx.act(f"Planned {len(field['timeline'])} weeks of fieldwork with {len(field['quality_control'])} quality-control rules.")
        return ctx.result({"fieldwork": field}, "After adoption, export the XLSForm and start the pilot.")


@register
class ResearchQAAgent(Agent):
    key = "research_qa"
    name = "Research QA"
    module = "research"
    description = "Checks the specification's quality gates on designs and on analysis outputs."
    tools = frozenset({"project.read", "evidence.read"})
    covers = ("Research QA Agent",)

    def run(self, ctx: AgentContext) -> AgentResult:
        phase = ctx.state.get("phase", "design")
        checks = self._design_checks(ctx) if phase == "design" else self._analysis_checks(ctx)
        failed = [c for c in checks if c["status"] == "violated"]
        warnings = [c for c in checks if c["status"] == "warning"]
        for c in failed + warnings:
            ctx.uncertainties.append(f"{c['name']}: {c['detail']}")
        ctx.act(f"Ran {len(checks)} quality checks: {len(failed)} failed, {len(warnings)} warnings.")
        if phase == "design":
            ctx.state.setdefault("package", {})["qa"] = {"checks": checks}
        next_step = ("Fix the failed checks before adopting." if failed else
                     "Approve the design package to create the research plan." if phase == "design" else
                     "Review draft insights and verdicts in the approvals inbox.")
        return ctx.result({"checks": checks, "passed": not failed}, next_step)

    def _design_checks(self, ctx: AgentContext) -> list[dict[str, Any]]:
        package = ctx.state.get("package") or {}
        design = package.get("design") or {}
        questions = (package.get("questionnaire") or {}).get("questions", [])
        codes = {q["code"] for q in questions}
        construct_codes = {c["code"] for c in design.get("constructs", [])}
        checks = []
        short = [c["code"] for c in design.get("constructs", []) if len(c["items"]) < 3]
        checks.append({"name": "Items per construct", "status": "violated" if short else "ok",
                       "detail": f"Fewer than 3 items: {', '.join(short)}" if short else "Every construct has 3 or more items."})
        known = construct_codes | codes | {"WTP", "origin"}
        orphans = [h["code"] for h in design.get("hypotheses", []) if h["iv"] not in known or h["dv"] not in known]
        checks.append({"name": "Hypotheses map to measures", "status": "violated" if orphans else "ok",
                       "detail": f"Unmapped: {', '.join(orphans)}" if orphans else "Every hypothesis maps to measured variables."})
        causal = [h["code"] for h in design.get("hypotheses", []) if causal_terms(h["statement"])]
        checks.append({"name": "Associational wording", "status": "warning" if causal else "ok",
                       "detail": f"Causal wording in {', '.join(causal)}" if causal else "Hypotheses use associational wording."})
        pricing = "pricing" in (package.get("framing") or {}).get("intents", [])
        has_price = any(c.startswith("vw_") for c in codes) and any(c.startswith("gg_") for c in codes)
        checks.append({"name": "Price module", "status": "ok" if (has_price or not pricing) else "violated",
                       "detail": "Van Westendorp and Gabor-Granger included." if has_price else
                       ("Not needed." if not pricing else "Pricing question without a price module.")})
        if pricing:
            checks.append({"name": "Hypothetical bias", "status": "warning",
                           "detail": "Stated willingness to pay overstates real behavior; plan a behavioral price test."})
        checks.append({"name": "Attention check", "status": "ok" if "attention_check" in codes else "warning",
                       "detail": "Included." if "attention_check" in codes else "No attention check item."})
        checks.append({"name": "Screening", "status": "ok" if any(c.startswith("screen_") for c in codes) else "warning",
                       "detail": "Screening question terminates non-qualified respondents."})
        sampling = package.get("sampling") or {}
        rec = (sampling.get("sample_size") or {}).get("recommended", 0)
        need = (sampling.get("sample_size") or {}).get("regression_minimum", 0)
        checks.append({"name": "Sample size for planned analyses", "status": "ok" if rec >= need else "violated",
                       "detail": f"Recommended n = {rec}; regression rule of thumb needs {need}."})
        if "contact_email" in codes:
            checks.append({"name": "Personal data separated", "status": "ok",
                           "detail": "Contact details are optional, stored separately and pseudonymized during cleaning."})
        return checks

    def _analysis_checks(self, ctx: AgentContext) -> list[dict[str, Any]]:
        from sqlalchemy import select

        from ..models import Analysis, Insight

        db, pid = ctx.db, ctx.project.id
        analyses = db.scalars(select(Analysis).where(Analysis.project_id == pid)).all()
        insights = db.scalars(select(Insight).where(Insight.project_id == pid)).all()
        evidence = ctx.tool("evidence.read")()
        checks = []
        missing = [a.title for a in analyses if not a.assumptions]
        checks.append({"name": "Assumption checks present", "status": "violated" if missing else "ok",
                       "detail": f"Missing for: {', '.join(missing)}" if missing else f"All {len(analyses)} analyses report assumption checks."})
        violated = [f"{a.title}: {c['name']}" for a in analyses for c in a.assumptions if c["status"] == "violated"]
        checks.append({"name": "Assumption violations", "status": "warning" if violated else "ok",
                       "detail": "; ".join(violated[:5]) if violated else "No violated assumptions."})
        uncited = [i.code for i in insights if not i.evidence]
        checks.append({"name": "Insights cite evidence", "status": "violated" if uncited else "ok",
                       "detail": f"Uncited: {', '.join(uncited)}" if uncited else "Every insight cites evidence."})
        weak = [e.code for e in evidence if e.strength in ("weak", "insufficient")]
        checks.append({"name": "Evidence strength", "status": "warning" if len(weak) > len(evidence) / 2 else "ok",
                       "detail": f"{len(weak)} of {len(evidence)} evidence records are weak or insufficient."})
        if any(a.method in ("van_westendorp", "gabor_granger", "wtp") for a in analyses):
            checks.append({"name": "Hypothetical bias", "status": "warning",
                           "detail": "Price findings are stated preferences. Validate with a pre-sale or A/B price test."})
        synthetic = any(e.origin == "synthetic_demo" for e in evidence)
        if synthetic:
            checks.append({"name": "Synthetic data", "status": "warning",
                           "detail": "Evidence comes from synthetic demo data and must not inform real decisions."})
        return checks


# ----------------------------------------------------------------------------------------------------
# Analysis pipeline
# ----------------------------------------------------------------------------------------------------


@register
class DataQualityAgent(Agent):
    key = "data_quality"
    name = "Data Quality"
    module = "research"
    description = "Profiles the dataset: missing data, duplicates, straight-lining, speeders, ranges, outliers, personal data."
    tools = frozenset({"dataset.read", "dataset.profile"})
    covers = ("Data Import Agent", "Data Quality Agent")

    def run(self, ctx: AgentContext) -> AgentResult:
        dataset, version = ctx.tool("dataset.read")(ctx.state.get("dataset_id"))
        ctx.state["dataset_id"] = dataset.id
        report = ctx.tool("dataset.profile")(version)
        issues = report.get("issues", [])
        by_sev = {s: sum(1 for i in issues if i["severity"] == s) for s in ("high", "medium", "low")}
        ctx.act(f"Found {len(issues)} issues (high {by_sev['high']}, medium {by_sev['medium']}, low {by_sev['low']}); "
                f"{report.get('flagged_respondents', 0)} respondents flagged; quality score {report.get('quality_score')}.")
        return ctx.result({"dataset_id": dataset.id, "version_id": version.id, "quality_score": report.get("quality_score"),
                           "issues": [{"check": i["check"], "severity": i["severity"], "count": i["count"],
                                       "message": i["message"]} for i in issues]},
                          "Review the proposed cleaning plan.")


@register
class DataCleaningAgent(Agent):
    key = "data_cleaning"
    name = "Data Cleaning"
    module = "research"
    description = "Proposes a cleaning plan from the diagnostics. A person must approve it before it is applied."
    tools = frozenset({"dataset.read", "cleaning.propose"})
    requires_approval = True
    covers = ("Data Cleaning Agent",)

    def run(self, ctx: AgentContext) -> AgentResult:
        _dataset, version = ctx.tool("dataset.read")(ctx.state.get("dataset_id"))
        plan = ctx.tool("cleaning.propose")(version.quality or {})
        if not plan:
            ctx.act("No cleaning needed.")
            return ctx.result({"operations": []}, "Continue to statistical analysis.")
        for op in plan:
            detail = op.get("reason") or op.get("column") or ", ".join(op.get("columns", []))
            ctx.act(f"Proposed {op['op']}" + (f" ({len(op['rows'])} rows)" if "rows" in op else "") + (f": {detail}" if detail else ""))
        ctx.state["cleaning_request"] = {"parent_version_id": version.id, "operations": plan}
        ctx.assumptions.append("Flagged respondents are dropped; outliers are kept because extreme values can be valid.")
        return ctx.result({"parent_version_id": version.id, "operations": plan},
                          "Approve the cleaning plan to continue the workflow.", status="awaiting_approval")


@register
class StatisticalAnalysisAgent(Agent):
    key = "statistical_analysis"
    name = "Statistical Analysis"
    module = "research"
    description = "Computes construct scores, descriptives, reliability and the hypothesis tests in the analysis plan."
    tools = frozenset({"project.read", "dataset.read", "dataset.derive_scores", "analysis.run", "evidence.create"})
    covers = ("Statistical Analysis Agent", "EDA Agent", "Regression Agent")

    def run(self, ctx: AgentContext) -> AgentResult:
        project = ctx.tool("project.read")()
        _dataset, version = ctx.tool("dataset.read")(ctx.state.get("dataset_id"))
        version = ctx.tool("dataset.derive_scores")(version)
        ctx.state["version_id"] = version.id
        columns = {c["name"] for c in version.columns}
        constructs = [c for c in project["constructs"] if c.code in columns]
        variables = project["variables"]
        run, save = ctx.tool("analysis.run"), ctx.tool("evidence.create")
        analyses = []

        desc_cols = [c.code for c in constructs] + [v for v in ("origin", "age_group", "discovery_channel") if v in columns]
        if desc_cols:
            analyses.append(run(version, "descriptive", {"columns": desc_cols}, "Descriptive statistics: key variables"))
        for c in constructs:
            items = sorted(n for n, v in variables.items() if v.construct_id == c.id and n != c.code and n in columns)
            if len(items) >= 2:
                a = run(version, "reliability", {"items": items, "scale_name": c.name})
                save(a)
                analyses.append(a)
        wtp_var = next((n for n in sorted(columns) if n.startswith("wtp_")), None)
        by_dv: dict[str, list[str]] = {}
        for h in project["hypotheses"]:
            method = self._method_for(h)
            if method == "regression_ols" and h.iv in columns and h.dv in columns:
                by_dv.setdefault(h.dv, []).append(h.iv)
            elif method == "mediation" and {h.iv, h.mediator, h.dv} <= columns:
                a = run(version, "mediation", {"x": h.iv, "m": h.mediator, "y": h.dv, "n_boot": 5000})
                save(a)
                analyses.append(a)
            elif method == "regression_logistic" and wtp_var and h.iv in columns:
                predictors = [h.iv] + [p for p in ("PV",) if p in columns and p != h.iv]
                a = run(version, "regression_logistic", {"dv": wtp_var, "predictors": predictors, "positive": "Ya"})
                save(a, [f"logit:{wtp_var}:{h.iv}", f"logit_model:{wtp_var}"])
                analyses.append(a)
            elif method == "crosstab" and wtp_var and h.iv in columns:
                a = run(version, "crosstab", {"row": h.iv, "col": wtp_var})
                save(a)
                analyses.append(a)
        for dv, ivs in by_dv.items():
            a = run(version, "regression_ols", {"dv": dv, "predictors": sorted(set(ivs))})
            save(a)
            analyses.append(a)
        ctx.state["analysis_ids"] = ctx.state.get("analysis_ids", []) + [a.id for a in analyses]
        ctx.assumptions.append("Construct scores are item means (listwise within construct, at most one item missing).")
        return ctx.result({"version_id": version.id, "analyses": [{"id": a.id, "method": a.method, "summary": a.result["summary"]}
                                                                   for a in analyses]},
                          "Continue to price sensitivity analysis.")

    @staticmethod
    def _method_for(h) -> str:
        if h.mediator:
            return "mediation"
        if h.dv == "WTP" and h.iv == "origin":
            return "crosstab"
        if h.dv == "WTP":
            return "regression_logistic"
        return "regression_ols"


@register
class PriceSensitivityAgent(Agent):
    key = "price_sensitivity"
    name = "Price Sensitivity"
    module = "research"
    description = "Van Westendorp, Gabor-Granger and willingness to pay at the target price by visitor group."
    tools = frozenset({"project.read", "dataset.read", "dataset.load", "analysis.run", "evidence.create"})
    covers = ("Price Sensitivity Agent",)

    def run(self, ctx: AgentContext) -> AgentResult:
        from ..research.design import parse_question

        project = ctx.tool("project.read")()
        _dataset, version = ctx.tool("dataset.read")(ctx.state.get("dataset_id"))
        df = ctx.tool("dataset.load")(version)
        target = parse_question(project["business_question"], project["currency"]).price
        run, save = ctx.tool("analysis.run"), ctx.tool("evidence.create")
        outputs: dict[str, Any] = {}
        vw = detect_vw_columns(df)
        if vw:
            a = run(version, "van_westendorp", {**vw, "target_price": target})
            save(a)
            outputs["van_westendorp"] = a.result["summary"]
        else:
            ctx.uncertainties.append("No Van Westendorp columns found.")
        ladder = {}
        for col in df.columns:
            m = re.fullmatch(r"(?:gg|wtp)_(\d+)(k?)", str(col))
            if m:
                ladder[str(float(m.group(1)) * (1000 if m.group(2) else 1))] = str(col)
        if len(ladder) >= 3:
            a = run(version, "gabor_granger", {"price_columns": ladder, "target_price": target})
            save(a)
            outputs["gabor_granger"] = a.result["summary"]
        wtp_var = next((c for c in df.columns if str(c).startswith("wtp_")), None)
        if wtp_var and target:
            group = "origin" if "origin" in df.columns else None
            a = run(version, "wtp", {"column": wtp_var, "price": target, "group": group, "positive": "Ya"})
            save(a)
            outputs["wtp"] = a.result["summary"]
        ctx.assumptions.append("Stated willingness to pay; real purchase rates are usually lower.")
        return ctx.result(outputs, "Continue to segmentation.")


@register
class SegmentationAgent(Agent):
    key = "segmentation"
    name = "Segmentation"
    module = "research"
    description = "k-means segmentation on construct scores with a stated objective, stability checks and personas."
    tools = frozenset({"project.read", "dataset.read", "analysis.run", "evidence.create"})
    covers = ("Segmentation Agent",)

    def run(self, ctx: AgentContext) -> AgentResult:
        project = ctx.tool("project.read")()
        _dataset, version = ctx.tool("dataset.read")(ctx.state.get("dataset_id"))
        columns = {c["name"] for c in version.columns}
        variables = [c.code for c in project["constructs"] if c.code in columns]
        if len(variables) < 2:
            ctx.uncertainties.append("Fewer than two construct scores available; segmentation skipped.")
            return ctx.result({}, "Continue to text analytics.", status="skipped")
        framing = project["plans"].get("framing") or {}
        objective = next((o for o in framing.get("objectives", []) if "segment" in o.lower()),
                         "Profile customer segments to guide targeting, packaging and communication.")
        rationale = ("Constructs from the conceptual framework (" + ", ".join(variables) +
                     ") capture the perceptions associated with willingness to pay.")
        profile = [c for c in ("origin", "age_group", "discovery_channel", "income_level") if c in columns]
        profile += [c for c in sorted(columns) if c.startswith("wtp_")][:1]
        text_col = next((c for c in ("worth_it_comment",) if c in columns), None)
        a = ctx.tool("analysis.run")(version, "segmentation", {"variables": variables, "objective": objective,
                                                               "rationale": rationale, "profile_columns": profile,
                                                               "text_column": text_col})
        ctx.tool("evidence.create")(a)
        ctx.used(f"objective: {objective}")
        return ctx.result({"summary": a.result["summary"],
                           "personas": [s["persona"] for s in a.result["data"]["segments"]]},
                          "Continue to text analytics.")


class ThemeLabels(BaseModel):
    labels: list[str] = Field(description="One short, human-readable theme name per theme, same order")


@register
class TextAnalyticsAgent(Agent):
    key = "text_analytics"
    name = "Text Analytics"
    module = "research"
    description = "Themes, keywords and sentiment in open-ended answers, with representative quotes."
    tools = frozenset({"project.read", "dataset.read", "analysis.run", "evidence.create", "llm.generate"})
    covers = ("Text Analytics Agent", "Sentiment Agent", "Thematic Analysis Agent")

    def run(self, ctx: AgentContext) -> AgentResult:
        project = ctx.tool("project.read")()
        _dataset, version = ctx.tool("dataset.read")(ctx.state.get("dataset_id"))
        text_cols = [n for n, v in project["variables"].items() if v.var_type == "text" and "email" not in n
                     and n in {c["name"] for c in version.columns}]
        if not text_cols:
            text_cols = [c["name"] for c in version.columns if (c.get("type") or c.get("inferred_type")) == "text"
                         and "email" not in c["name"]]
        if not text_cols:
            return ctx.result({}, "Continue to insights.", status="skipped")
        col = text_cols[0]
        themes = ctx.tool("analysis.run")(version, "text_themes", {"text_column": col, "n_topics": 5})
        ctx.tool("evidence.create")(themes, [e["key"] for e in themes.result["evidence_candidates"][:3]])
        sentiment = ctx.tool("analysis.run")(version, "sentiment", {"text_column": col,
                                                                     "group": "origin" if "origin" in {c["name"] for c in version.columns} else None})
        ctx.tool("evidence.create")(sentiment)
        topics = themes.result["data"]["themes"]
        suggestions = None
        refined = ctx.tool("llm.generate")(
            system="You are the Thematic Analysis agent. Name each theme in 2 to 5 words, based on its terms and examples.",
            prompt="\n".join(f"Theme {i + 1}: terms {[t['term'] for t in th['terms'][:6]]}; examples "
                             f"{wrap_untrusted(' | '.join(th['examples'][:2]), 600)}" for i, th in enumerate(topics)),
            schema=ThemeLabels, max_tokens=1500)
        if refined is not None and len(refined.labels) == len(topics):
            suggestions = refined.labels
            ctx.act("Claude suggested theme names; they are stored as suggestions for the researcher to confirm.")
        return ctx.result({"column": col, "themes": [t["label"] for t in topics], "suggested_names": suggestions,
                           "sentiment": sentiment.result["summary"]}, "Continue to insight generation.")


class InsightWording(BaseModel):
    statements: list[str] = Field(description="One improved statement per draft insight, same order and meaning")


@register
class InsightAgent(Agent):
    key = "insight"
    name = "Insight"
    module = "research"
    description = "Drafts evidence-linked insights and proposes hypothesis verdicts for human approval."
    tools = frozenset({"project.read", "evidence.read", "insight.propose", "verdict.propose", "recommendation.propose",
                       "llm.generate"})
    requires_approval = True
    covers = ("Insight Agent", "Evidence Agent")

    def run(self, ctx: AgentContext) -> AgentResult:
        project = ctx.tool("project.read")()
        evidence = ctx.tool("evidence.read")()
        keyed = ev_by_key(evidence)
        drafts = self._drafts(keyed, project)
        refined = None
        if drafts:
            refined = ctx.tool("llm.generate")(
                system="You are the Insight agent. Make each statement clearer for a manager. Keep every number exactly; "
                       "add no new numbers; keep associational wording.",
                prompt="\n".join(f"{i + 1}. {d['statement']}" for i, d in enumerate(drafts)),
                schema=InsightWording, max_tokens=3000)
        created = []
        for i, d in enumerate(drafts):
            statement, model_generated = d["statement"], False
            if refined is not None and len(refined.statements) == len(drafts):
                candidate = refined.statements[i]
                allowed = allowed_numbers([d["statement"]] + [e.statement for e in d["evidence"]])
                if not ungrounded_numbers(candidate, allowed) and not causal_terms(candidate):
                    statement, model_generated = candidate, True
                else:
                    ctx.uncertainties.append(f"Model wording for '{d['title']}' failed the grounding or causal-language check.")
            ins = ctx.tool("insight.propose")(title=d["title"], statement=statement, evidence_ids=[e.id for e in d["evidence"]],
                                              implication=d.get("implication", ""), confidence=d["confidence"],
                                              uncertainty=d["uncertainty"], is_model_generated=model_generated)
            ctx.cite(*[e.code for e in d["evidence"]])
            created.append(ins.code)
        verdicts = self._verdicts(ctx, project, keyed)
        recs = self._recommendations(ctx, keyed, project)
        ctx.act(f"Drafted {len(created)} insights, proposed {len(verdicts)} verdicts and {len(recs)} recommendations.")
        return ctx.result({"insights": created, "verdicts": verdicts, "recommendations": recs},
                          "Review and approve insights, verdicts and recommendations.", status="succeeded")

    @staticmethod
    def _confidence(evidence) -> str:
        ranks = {"strong": 3, "moderate": 2, "weak": 1, "insufficient": 0}
        low = min(ranks.get(e.strength, 1) for e in evidence)
        return "high" if low >= 3 else "medium" if low >= 2 else "low"

    def _drafts(self, keyed: dict[str, Any], project: dict[str, Any]) -> list[dict[str, Any]]:
        drafts = []
        price_ev = [keyed[k] for k in ("vw:target", "gg:target") if k in keyed]
        wtp_key = next((k for k in keyed if k.startswith("wtp:") and ":by:" not in k), None)
        if wtp_key:
            price_ev.insert(0, keyed[wtp_key])
        if price_ev:
            drafts.append({"title": "Reaction to the target price", "evidence": price_ev,
                           "statement": " ".join(e.statement for e in price_ev[:2]),
                           "implication": "Use the acceptable range to set the launch price and test it with real bookings.",
                           "confidence": self._confidence(price_ev),
                           "uncertainty": "Stated willingness to pay usually overstates real purchasing."})
        by_group = next((keyed[k] for k in keyed if k.startswith("wtp:") and ":by:" in k), None)
        if by_group:
            drafts.append({"title": "Willingness to pay differs by visitor group", "evidence": [by_group],
                           "statement": by_group.statement,
                           "implication": "Consider group-specific packages or channels rather than one price for all.",
                           "confidence": self._confidence([by_group]),
                           "uncertainty": "Group sizes differ; smaller groups have wider intervals."})
        drivers = [e for k, e in keyed.items() if k.startswith("ols:") and (e.p_value or 1) < 0.05]
        if drivers:
            drafts.append({"title": "Perceptions associated with purchase intention", "evidence": drivers,
                           "statement": " ".join(e.statement for e in drivers[:2]),
                           "implication": "Communicate the benefits that raise perceived value.",
                           "confidence": self._confidence(drivers),
                           "uncertainty": "Cross-sectional associations; they do not prove what drives behavior."})
        mediation = [e for k, e in keyed.items() if k.startswith("mediation:")]
        if mediation:
            drafts.append({"title": "Authenticity works through perceived value", "evidence": mediation,
                           "statement": mediation[0].statement,
                           "implication": "Make authenticity visible as value (what guests get), not only as heritage.",
                           "confidence": self._confidence(mediation),
                           "uncertainty": "Mediation on survey data shows a pattern consistent with, not proof of, a mechanism."})
        seg = keyed.get("segmentation")
        if seg:
            drafts.append({"title": "Distinct customer segments", "evidence": [seg], "statement": seg.statement,
                           "implication": "Target and message each segment separately.", "confidence": self._confidence([seg]),
                           "uncertainty": "Segments depend on the chosen variables; validate against behavior."})
        themes = [e for k, e in keyed.items() if k.startswith("theme:")][:2]
        if themes:
            drafts.append({"title": "What would make the experience worth the price", "evidence": themes,
                           "statement": " ".join(e.statement for e in themes),
                           "implication": "Design the offer around the most frequent themes.", "confidence": "medium",
                           "uncertainty": "Theme labels are term-based and should be confirmed by reading the answers."})
        return drafts

    def _verdicts(self, ctx: AgentContext, project: dict[str, Any], keyed: dict[str, Any]) -> list[str]:
        out = []
        for h in project["hypotheses"]:
            if h.status not in ("untested",):
                continue
            ev, verdict, why = self._match(h, keyed)
            if not ev:
                continue
            ctx.tool("verdict.propose")(h, verdict, [ev.id], why)
            out.append(f"{h.code}: {verdict}")
        return out

    @staticmethod
    def _match(h, keyed: dict[str, Any]):
        def verdict_from(e, positive: bool):
            p = e.p_value
            if p is None:
                return "inconclusive"
            value = e.value or {}
            effect = value.get("b")
            if effect is None:
                effect = (value["odds_ratio"] - 1) if "odds_ratio" in value else (e.effect_size or 0)
            right_direction = (effect > 0) == positive
            if p < 0.05 and right_direction:
                return "supported"
            if p < 0.05:
                return "not_supported"
            return "inconclusive" if p < 0.10 else "not_supported"

        if h.mediator:
            e = keyed.get(f"mediation:{h.iv}:{h.mediator}:{h.dv}")
            if e:
                low, high = e.ci_low or 0, e.ci_high or 0
                verdict = "supported" if (low > 0 or high < 0) and (low > 0) == (h.expected_direction != "negative") else "not_supported"
                return e, verdict, f"Bootstrap interval {low:.3f} to {high:.3f} {'excludes' if low > 0 or high < 0 else 'includes'} zero."
            return None, None, None
        if h.dv == "WTP" and h.iv == "origin":
            e = next((v for k, v in keyed.items() if k.startswith("crosstab:origin:")), None)
            by = next((v for k, v in keyed.items() if k.startswith("wtp:") and ":by:" in k), None)
            if e:
                groups = {g["group"].lower(): g["share"] for g in (by.value or {}).get("groups", [])} if by else {}
                higher = groups.get("international", 0) > groups.get("domestic", 0) if groups else True
                verdict = "supported" if (e.p_value or 1) < 0.05 and higher else "not_supported"
                return e, verdict, e.statement
            return None, None, None
        if h.dv == "WTP":
            e = next((v for k, v in keyed.items() if k.startswith("logit:") and k.endswith(f":{h.iv}")), None)
            if e:
                return e, verdict_from(e, h.expected_direction != "negative"), e.statement
            return None, None, None
        e = keyed.get(f"ols:{h.dv}:{h.iv}")
        if e:
            return e, verdict_from(e, h.expected_direction != "negative"), e.statement
        return None, None, None

    def _recommendations(self, ctx: AgentContext, keyed: dict[str, Any], project: dict[str, Any]) -> list[str]:
        recs = []
        target_ev = keyed.get("vw:target") or next((v for k, v in keyed.items() if k.startswith("wtp:") and ":by:" not in k), None)
        if target_ev:
            rec = ctx.tool("recommendation.propose")(
                statement=("Launch within the acceptable price range and validate the target price with a real-behavior "
                           "test (for example a pre-sale page at two price points) before committing."),
                evidence_ids=[target_ev.id], rationale="Stated willingness to pay needs behavioral confirmation.",
                module="research", priority="high", is_model_generated=False)
            recs.append(rec.code)
        by_group = next((v for k, v in keyed.items() if k.startswith("wtp:") and ":by:" in k), None)
        if by_group:
            rec = ctx.tool("recommendation.propose")(
                statement="Design a package or channel strategy for the most price-sensitive visitor group, "
                          "and reach the least price-sensitive group through the channels they use.",
                evidence_ids=[by_group.id], module="strategy", priority="medium", is_model_generated=False)
            recs.append(rec.code)
        return recs


@register
class ReportAgent(Agent):
    key = "report"
    name = "Report"
    module = "research"
    description = "Composes the research report with evidence citations, methods and data appendices."
    tools = frozenset({"project.read", "evidence.read", "report.compose"})
    requires_approval = True
    covers = ("Report Agent",)

    def run(self, ctx: AgentContext) -> AgentResult:
        report = ctx.tool("report.compose")("research_report")
        ctx.act(f"Composed '{report.title}' (version {report.version}) citing {len(report.evidence_ids)} evidence records.")
        ctx.assumptions.append("Draft insights and recommendations are labeled as drafts until approved.")
        return ctx.result({"report_id": report.id, "title": report.title},
                          "Review the report; finalize it after approving the insights.", status="succeeded")
