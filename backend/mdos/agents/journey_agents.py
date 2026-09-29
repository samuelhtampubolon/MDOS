"""Journey Designer agents: voice of customer, journey mapping, pain points, opportunities, simulation, experiments."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .base import Agent, register
from .contract import AgentBlocked, AgentContext, AgentResult
from .grounding import wrap_untrusted


@register
class VoiceOfCustomerAgent(Agent):
    key = "voice_of_customer"
    name = "Voice of Customer"
    module = "journey"
    description = "Maps reviews and comments to journey stages, scores emotion and extracts pain points with quotes."
    tools = frozenset({"dataset.read", "voc.analyze"})
    covers = ("Voice of Customer Agent",)

    def run(self, ctx: AgentContext) -> AgentResult:
        dataset, version = ctx.tool("dataset.read")(ctx.state.get("reviews_dataset_id"), kind="reviews")
        text_col = ctx.state.get("text_column")
        if not text_col:
            text_col = next((c["name"] for c in version.columns if (c.get("type") or c.get("inferred_type")) == "text"), None)
        if not text_col:
            raise AgentBlocked("The reviews dataset has no text column.")
        rating = ctx.state.get("rating_column") or next((c["name"] for c in version.columns if c["name"] in ("rating", "stars")), None)
        analysis, evidence = ctx.tool("voc.analyze")(version, text_col, ctx.state.get("template", "tourism"), rating)
        ctx.state.update({"voc_analysis_id": analysis.id, "voc_evidence_ids": [e.id for e in evidence]})
        ctx.act(analysis.result["summary"])
        ctx.assumptions.append("Online reviews over-represent strong opinions.")
        return ctx.result({"analysis_id": analysis.id, "summary": analysis.result["summary"]}, "Build the journey map.")


@register
class JourneyMappingAgent(Agent):
    key = "journey_mapping"
    name = "Journey Mapping"
    module = "journey"
    description = "Creates the journey from a stage template and applies the voice-of-customer findings."
    tools = frozenset({"journey.read", "journey.propose"})
    requires_approval = False
    covers = ("Journey Mapping Agent",)

    def run(self, ctx: AgentContext) -> AgentResult:
        from ..models import Analysis, Evidence

        journey = ctx.tool("journey.propose")("create", name=ctx.state.get("journey_name", "Customer journey"),
                                              template=ctx.state.get("template", "tourism"))
        analysis = ctx.db.get(Analysis, ctx.state["voc_analysis_id"])
        evidence = [ctx.db.get(Evidence, i) for i in ctx.state.get("voc_evidence_ids", [])]
        ctx.tool("journey.propose")("apply_voc", journey=journey, analysis=analysis, evidence=[e for e in evidence if e])
        ctx.db.flush()
        ctx.db.refresh(journey)
        ctx.state["journey_id"] = journey.id
        ctx.act(f"Created '{journey.name}' with {len(journey.stages)} stages and {len(journey.touchpoints)} touchpoints.")
        ctx.assumptions.append("Stage conversion rates are template defaults; replace them with analytics data.")
        return ctx.result({"journey_id": journey.id}, "Review pain points and the emotion curve.")


@register
class PainPointAgent(Agent):
    key = "pain_point"
    name = "Pain Point"
    module = "journey"
    description = "Prioritizes pain points (frequency x severity x reach) and reads the emotion curve and friction heatmap."
    tools = frozenset({"journey.read"})
    covers = ("Pain Point Agent", "Emotion Mapping Agent")

    def run(self, ctx: AgentContext) -> AgentResult:
        journey = ctx.tool("journey.read")(ctx.state["journey_id"])
        pains = sorted(journey.pain_points, key=lambda p: -p.score)
        for p in pains[:5]:
            ctx.act(f"{p.title}: score {p.score:.1f} ({p.mentions} reviews, severity {p.severity:.2f}).")
        low = min((s for s in journey.stages if s.get("emotion") is not None and s.get("mentions", 0) >= 5),
                  key=lambda s: s["emotion"], default=None)
        high = max((s for s in journey.stages if s.get("emotion") is not None and s.get("mentions", 0) >= 5),
                   key=lambda s: s["emotion"], default=None)
        if low and high:
            ctx.act(f"Emotional low point: {low['name']} ({low['emotion']:+.2f}); high point: {high['name']} ({high['emotion']:+.2f}).")
        from ..models import Evidence

        ids = [e for p in pains[:5] for e in (p.evidence_ids or [])]
        ctx.cite(*[ev.code for ev in (ctx.db.get(Evidence, i) for i in ids) if ev])
        return ctx.result({"top_pain_points": [{"title": p.title, "score": p.score} for p in pains[:5]],
                           "low_point": low["name"] if low else None, "high_point": high["name"] if high else None},
                          "Generate interventions for the top pain points.")


class StoryConcept(BaseModel):
    title: str = Field(description="Short title for the intervention")
    description: str = Field(description="Two or three sentences describing what guests experience")


@register
class ExperienceOpportunityAgent(Agent):
    key = "experience_opportunity"
    name = "Experience Opportunity"
    module = "journey"
    description = "Turns top pain points into interventions, including storytelling concepts and conversion fixes."
    tools = frozenset({"journey.read", "journey.propose", "llm.generate"})
    covers = ("UX Opportunity Agent", "Storytelling Agent", "Conversion Optimization Agent")

    def run(self, ctx: AgentContext) -> AgentResult:
        journey = ctx.tool("journey.read")(ctx.state["journey_id"])
        created = ctx.tool("journey.propose")("interventions", journey=journey)
        for iv in created:
            if iv.kind == "satisfaction_uplift":
                pain = next((p for p in journey.pain_points if p.id == iv.pain_point_id), None)
                quotes = " | ".join((pain.quotes or [])[:3]) if pain else ""
                concept = ctx.tool("llm.generate")(
                    system="You are the Storytelling agent. Design the opening of a cultural experience around local "
                           "storytelling. Be concrete and respectful of local culture. Do not invent statistics.",
                    prompt=f"Pain point: {iv.title}. Guest quotes: {wrap_untrusted(quotes, 1200)}",
                    schema=StoryConcept, max_tokens=1500)
                if concept is not None:
                    iv.description = f"{concept.description} (Concept drafted by Claude; review with local storytellers.)"
                    ctx.act("Claude drafted the storytelling concept for the first 15 minutes.")
            ctx.act(f"Proposed '{iv.title}' at the {iv.stage_key} stage (uplift {iv.uplift_low:.0%} to {iv.uplift_high:.0%}).")
        ctx.state["intervention_ids"] = [iv.id for iv in created]
        ctx.assumptions.append("Uplift ranges come from an intervention library and are hypotheses to test.")
        return ctx.result({"interventions": [{"id": iv.id, "title": iv.title} for iv in created]},
                          "Simulate the interventions before prioritizing.")


@register
class JourneySimulationAgent(Agent):
    key = "journey_simulation"
    name = "Journey Simulation"
    module = "journey"
    description = "Simulates each intervention's before-and-after effect with low, mid and high estimates."
    tools = frozenset({"journey.read", "journey.simulate"})
    covers = ("Journey Simulation Agent",)

    def run(self, ctx: AgentContext) -> AgentResult:
        journey = ctx.tool("journey.read")(ctx.state["journey_id"])
        ranked = []
        for iv in journey.interventions:
            sim = ctx.tool("journey.simulate")(journey, iv)
            mid = sim["levels"]["mid"]
            ranked.append((mid["delta_customers"], iv))
            ctx.act(f"{iv.title}: +{mid['delta_customers']:.0f} customers per period (mid estimate; low "
                    f"{sim['levels']['low']['delta_customers']:.0f}, high {sim['levels']['high']['delta_customers']:.0f}).")
        ranked.sort(key=lambda x: -x[0])
        ctx.state["ranked_interventions"] = [iv.id for _, iv in ranked]
        return ctx.result({"ranking": [{"id": iv.id, "title": iv.title, "delta_customers_mid": d} for d, iv in ranked]},
                          "Design experiments for the top interventions.")


@register
class ExperimentDesignAgent(Agent):
    key = "experiment_design"
    name = "Experiment Design"
    module = "journey"
    description = "Writes experiment briefs with hypothesis, metric, sample size and duration; launch needs approval."
    tools = frozenset({"journey.read", "experiment.propose"})
    requires_approval = True
    covers = ("Experiment Design Agent", "Experimental Design Agent")

    def run(self, ctx: AgentContext) -> AgentResult:
        journey = ctx.tool("journey.read")(ctx.state["journey_id"])
        by_id = {iv.id: iv for iv in journey.interventions}
        created = []
        for iv_id in ctx.state.get("ranked_interventions", [])[:2]:
            exp = ctx.tool("experiment.propose")(journey, by_id[iv_id])
            created.append(exp)
            ctx.act(f"Drafted '{exp.name}': {exp.sample_size_per_arm} per arm, about {exp.duration_days} days.")
            for note in (exp.results or {}).get("notes", []):
                ctx.uncertainties.append(note)
        return ctx.result({"experiments": [{"id": e.id, "name": e.name} for e in created]},
                          "Approve the experiments you want to launch; enter results when they finish.")
