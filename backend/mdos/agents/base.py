"""Agent base class and the registry of every agent named in the specification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from .contract import AgentContext, AgentResult


class Agent:
    key: ClassVar[str]
    name: ClassVar[str]
    module: ClassVar[str]
    description: ClassVar[str]
    tools: ClassVar[frozenset[str]]
    requires_approval: ClassVar[bool] = False
    covers: ClassVar[tuple[str, ...]] = ()

    def run(self, ctx: AgentContext) -> AgentResult:  # pragma: no cover - interface
        raise NotImplementedError


AGENTS: dict[str, type[Agent]] = {}


def register(cls: type[Agent]) -> type[Agent]:
    AGENTS[cls.key] = cls
    return cls


@dataclass(frozen=True)
class DeferredAgent:
    name: str
    module: str
    phase: str
    reason: str
    covered_by: tuple[str, ...] = field(default_factory=tuple)


DEFERRED = [
    DeferredAgent("PLS-SEM Agent", "research", "phase_2", "Needs the PLS-SEM engine; constructs and indicators already exist."),
    DeferredAgent("Conjoint Agent", "research", "phase_2", "Needs choice design generation and choice-model estimation."),
    DeferredAgent("Presentation Agent", "research", "phase_2", "PPTX export; MVP ships Markdown and HTML reports."),
    DeferredAgent("Literature Discovery Agent (full)", "research", "phase_2",
                  "Needs scholarly search APIs; the MVP cites sources from the curated construct library.",
                  ("research_design",)),
]

SPEC_AGENTS = {
    "research": ["Research Director Agent", "Problem Framing Agent", "Literature Discovery Agent", "Research Design Agent",
                 "Hypothesis Agent", "Measurement Agent", "Questionnaire Agent", "Sampling Agent", "Interview Guide Agent",
                 "Fieldwork Agent", "Data Import Agent", "Data Quality Agent", "Data Cleaning Agent", "EDA Agent",
                 "Statistical Analysis Agent", "Segmentation Agent", "Text Analytics Agent", "Sentiment Agent",
                 "Thematic Analysis Agent", "PLS-SEM Agent", "Regression Agent", "Experimental Design Agent", "Conjoint Agent",
                 "Price Sensitivity Agent", "Insight Agent", "Evidence Agent", "Report Agent", "Presentation Agent",
                 "Research QA Agent"],
    "strategy": ["Market Model Agent", "Competitor Agent", "Segmentation Strategy Agent", "Positioning Agent", "Pricing Agent",
                 "Media Allocation Agent", "Channel Strategy Agent", "Forecast Agent", "Scenario Agent", "Sensitivity Agent",
                 "Optimization Agent", "Strategy Narrative Agent"],
    "journey": ["Voice of Customer Agent", "Journey Mapping Agent", "Pain Point Agent", "Emotion Mapping Agent",
                "Storytelling Agent", "UX Opportunity Agent", "Conversion Optimization Agent", "Experiment Design Agent",
                "Journey Simulation Agent"],
}


def registry() -> dict[str, Any]:
    """Every specification agent, with the executable MVP agent that covers it or its deferral."""
    from . import journey_agents, research_agents, strategy_agents  # noqa: F401  (registration side effect)

    covered: dict[str, str] = {}
    for cls in AGENTS.values():
        for spec_name in cls.covers:
            covered[spec_name] = cls.key
    deferred = {d.name.replace(" (full)", ""): d for d in DEFERRED}
    rows = []
    for module, names in SPEC_AGENTS.items():
        for name in names:
            if name in covered:
                rows.append({"spec_agent": name, "module": module, "status": "mvp", "implemented_by": covered[name]})
            elif name in deferred:
                d = deferred[name]
                rows.append({"spec_agent": name, "module": module, "status": d.phase, "implemented_by": None, "reason": d.reason})
            else:
                rows.append({"spec_agent": name, "module": module, "status": "unmapped", "implemented_by": None})
    agents = [{"key": c.key, "name": c.name, "module": c.module, "description": c.description, "tools": sorted(c.tools),
               "requires_approval": c.requires_approval, "covers": list(c.covers)} for c in AGENTS.values()]
    return {"agents": agents, "spec_agents": rows,
            "counts": {"executable": len(agents), "spec_total": sum(len(v) for v in SPEC_AGENTS.values()),
                       "spec_covered": sum(1 for r in rows if r["status"] == "mvp"),
                       "deferred": sum(1 for r in rows if r["status"].startswith("phase"))}}
