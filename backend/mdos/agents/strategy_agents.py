"""Strategy Simulator agents: market model, pricing, media allocation, scenarios and the strategy narrative."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..research.language import causal_terms
from .base import Agent, register
from .contract import AgentContext, AgentResult
from .grounding import allowed_numbers, ungrounded_numbers


def _money(value: float, currency: str) -> str:
    if currency == "IDR":
        return "Rp " + f"{value:,.0f}".replace(",", ".")
    return f"{currency} {value:,.0f}"


@register
class MarketModelAgent(Agent):
    key = "market_model"
    name = "Market Model"
    module = "strategy"
    description = "Builds the baseline market model from research evidence plus labeled placeholder assumptions."
    tools = frozenset({"project.read", "evidence.read", "scenario.propose"})
    covers = ("Market Model Agent", "Competitor Agent", "Segmentation Strategy Agent", "Positioning Agent")

    def run(self, ctx: AgentContext) -> AgentResult:
        ctx.tool("project.read")()
        baseline, inputs = ctx.tool("scenario.propose")("baseline")
        ctx.state["baseline_id"] = baseline.id
        model = baseline.model
        evidence_backed = [a for a in model["assumptions"] if a.get("source") == "evidence"]
        guesses = [a for a in model["assumptions"] if a.get("source") == "guess"]
        for src in inputs.get("sources", []):
            ctx.used(f"{src['input']} (analysis {src['analysis_id'][:8]})")
        for a in guesses:
            ctx.assumptions.append(f"{a['label']}: {a.get('note') or 'placeholder, replace with your data'}")
        k = baseline.results["kpis"]
        ctx.act(f"Built the baseline: {len(model['segments'])} segments, {len(model['channels'])} channels, "
                f"price {_money(model['offer']['price'], model['currency'])}; {len(evidence_backed)} assumptions are "
                f"evidence-backed and {len(guesses)} are placeholders.")
        ctx.act(f"Baseline result: {k['customers']:.0f} customers, profit {_money(k['profit'], model['currency'])} per {model['period']}.")
        if not evidence_backed:
            ctx.uncertainties.append("No research evidence was available; the model runs entirely on placeholder assumptions.")
        return ctx.result({"baseline_id": baseline.id, "kpis": k, "evidence_backed": len(evidence_backed),
                           "placeholders": len(guesses)}, "Replace placeholder assumptions (market size, funnel rates) with your data.")


@register
class PricingAgent(Agent):
    key = "pricing"
    name = "Pricing"
    module = "strategy"
    description = "Price curve with revenue- and profit-maximizing prices, compared with the research acceptable range."
    tools = frozenset({"scenario.read", "scenario.simulate"})
    covers = ("Pricing Agent",)

    def run(self, ctx: AgentContext) -> AgentResult:
        baseline = next(s for s in ctx.tool("scenario.read")() if s.id == ctx.state["baseline_id"])
        curve = ctx.tool("scenario.simulate")("price_curve", baseline)
        currency = baseline.model["currency"]
        ctx.state["price_curve"] = {"revenue_max": curve["revenue_max_price"], "profit_max": curve["profit_max_price"]}
        ctx.act(f"Profit peaks near {_money(curve['profit_max_price'], currency)} and revenue near "
                f"{_money(curve['revenue_max_price'], currency)} (current {_money(curve['current_price'], currency)}).")
        ctx.assumptions.append("Prices outside the tested range extend the research demand curve linearly.")
        return ctx.result({"revenue_max_price": curve["revenue_max_price"], "profit_max_price": curve["profit_max_price"]},
                          "Compare these prices with the Van Westendorp acceptable range before deciding.")


@register
class MediaAllocationAgent(Agent):
    key = "media_allocation"
    name = "Media Allocation"
    module = "strategy"
    description = "Greedy marginal-return budget allocation across paid channels, saved as a scenario."
    tools = frozenset({"scenario.read", "scenario.simulate", "scenario.propose"})
    covers = ("Media Allocation Agent", "Channel Strategy Agent", "Optimization Agent")

    def run(self, ctx: AgentContext) -> AgentResult:
        baseline = next(s for s in ctx.tool("scenario.read")() if s.id == ctx.state["baseline_id"])
        opt = ctx.tool("scenario.simulate")("optimize_media", baseline)
        if not opt.get("levers"):
            return ctx.result({}, "No paid channels to optimize.", status="skipped")
        scenario = ctx.tool("scenario.propose")("scenario", baseline=baseline, name="Optimized media mix (same budget)",
                                                levers=opt["levers"], description=opt["note"])
        currency = baseline.model["currency"]
        for a in opt["allocation"]:
            ctx.act(f"{a['name']}: {_money(a['current'], currency)} to {_money(a['optimized'], currency)}.")
        ctx.uncertainties.append("Allocation depends on placeholder funnel rates; calibrate with campaign data first.")
        return ctx.result({"scenario_id": scenario.id, "allocation": opt["allocation"]},
                          "Treat the optimized mix as a hypothesis to test with a budget split experiment.")


@register
class ScenarioAgent(Agent):
    key = "scenario"
    name = "Scenario"
    module = "strategy"
    description = "Runs the Graph1 what-if scenarios, tornado sensitivity and Monte Carlo ranges on the baseline."
    tools = frozenset({"scenario.read", "scenario.propose", "scenario.simulate"})
    covers = ("Scenario Agent", "Forecast Agent", "Sensitivity Agent")

    def run(self, ctx: AgentContext) -> AgentResult:
        baseline = next(s for s in ctx.tool("scenario.read")() if s.id == ctx.state["baseline_id"])
        created = ctx.tool("scenario.propose")("what_ifs", baseline=baseline)
        currency = baseline.model["currency"]
        for s in created:
            d = s.results["comparison"]["profit"]
            ctx.act(f"{s.name}: profit {_money(d['scenario'], currency)} ({d['delta']:+,.0f} versus baseline).")
        sens = ctx.tool("scenario.simulate")("sensitivity", baseline)
        mc = ctx.tool("scenario.simulate")("monte_carlo", baseline, n=800)
        top = [r["label"] for r in sens["rows"][:3]]
        ctx.state["what_if_ids"] = [s.id for s in created]
        ctx.state["risk"] = {"top_drivers": top, "p_profit": mc["probability_profit_positive"], "profit": mc["profit"]}
        ctx.act(f"Largest profit drivers: {', '.join(top)}. Probability of profit: {mc['probability_profit_positive']:.0%}.")
        return ctx.result({"scenarios": [s.id for s in created], "top_drivers": top, "monte_carlo": mc["profit"],
                           "probability_profit_positive": mc["probability_profit_positive"]},
                          "Firm up the top drivers with data; they move profit the most.")


class Narrative(BaseModel):
    summary: str = Field(description="Three to five sentences for a manager, using only numbers from the context")


@register
class StrategyNarrativeAgent(Agent):
    key = "strategy_narrative"
    name = "Strategy Narrative"
    module = "strategy"
    description = "Explains the scenario results in plain language, cites evidence and proposes a decision for approval."
    tools = frozenset({"scenario.read", "evidence.read", "decision.propose", "llm.generate"})
    requires_approval = True
    covers = ("Strategy Narrative Agent",)

    def run(self, ctx: AgentContext) -> AgentResult:
        scenarios = ctx.tool("scenario.read")()
        baseline = next(s for s in scenarios if s.id == ctx.state["baseline_id"])
        children = [s for s in scenarios if s.baseline_id == baseline.id]
        currency = baseline.model["currency"]
        base_k = baseline.results["kpis"]
        best = max(children, key=lambda s: s.results["kpis"]["profit"], default=None)
        lines = [f"The evidence-based baseline yields about {base_k['customers']:.0f} customers and a profit of "
                 f"{_money(base_k['profit'], currency)} per {baseline.model['period']}."]
        for s in children:
            k = s.results["kpis"]
            lines.append(f"{s.name}: {k['customers']:.0f} customers, profit {_money(k['profit'], currency)}.")
        risk = ctx.state.get("risk") or {}
        if risk:
            lines.append(f"Across uncertain assumptions, the chance of a profit is {risk['p_profit']:.0%}; "
                         f"the biggest drivers are {', '.join(risk['top_drivers'])}.")
        deterministic = " ".join(lines)
        summary, model_generated = deterministic, False
        refined = ctx.tool("llm.generate")(
            system="You are the Strategy Narrative agent. Summarize the scenario results for a marketing manager.",
            prompt=f"Scenario results:\n{deterministic}\nExplain the trade-offs. Use only these numbers.",
            schema=Narrative, max_tokens=2000)
        if refined is not None:
            allowed = allowed_numbers([deterministic])
            if not ungrounded_numbers(refined.summary, allowed) and not causal_terms(refined.summary):
                summary, model_generated = refined.summary, True
            else:
                ctx.uncertainties.append("Model narrative introduced numbers or causal wording; used the deterministic summary.")
        evidence_ids = [a["evidence_id"] for a in baseline.model["assumptions"] if a.get("evidence_id")]
        decision = None
        if best and best.results["kpis"]["profit"] > base_k["profit"]:
            decision = ctx.tool("decision.propose")(
                title=f"Adopt scenario: {best.name}",
                decision=f"Proceed with '{best.name}' and validate it with an experiment before full rollout.",
                rationale=f"Highest simulated profit ({_money(best.results['kpis']['profit'], currency)}) among the scenarios.",
                scenario_id=best.id, evidence_ids=list(dict.fromkeys(evidence_ids)))
            ctx.act(f"Proposed a decision for approval: {decision.title}.")
        ctx.state["narrative"] = summary
        return ctx.result({"summary": summary, "model_generated": model_generated,
                           "decision_id": decision.id if decision else None},
                          "Review the proposed decision in the approvals inbox.")
