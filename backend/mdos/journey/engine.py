"""Journey simulation: acquisition funnel plus outcome loops (share, return, recommend).

Graph1: Journey -> Friction -> Intervention -> Expected behavioral effect -> Experiment.
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from ..analytics.power import ab_sample_size

DEFAULT_WOM = {"views_per_share": 40, "discover_per_view": 0.02, "referrals_per_recommender": 0.5}


def simulate(stages: list[dict[str, Any]], entrants: float, price: float, wom: dict[str, float] | None = None) -> dict[str, Any]:
    wom = {**DEFAULT_WOM, **(wom or {})}
    funnel = [s for s in stages if s.get("kind", "funnel") == "funnel"]
    outcomes = {s["key"]: s for s in stages if s.get("kind") == "outcome"}
    rows = []
    at_stage = float(entrants)
    for s in funnel:
        conv = float(s.get("conversion", 1.0))
        rows.append({"key": s["key"], "name": s["name"], "entering": at_stage, "conversion": conv, "continuing": at_stage * conv})
        at_stage *= conv
    customers = at_stage
    share_rate = float(outcomes.get("share", {}).get("rate", 0.0))
    return_rate = float((outcomes.get("return") or outcomes.get("retention") or {}).get("rate", 0.0))
    recommend_rate = float((outcomes.get("recommend") or outcomes.get("advocacy") or {}).get("rate", 0.0))
    sharers = customers * share_rate
    recommenders = customers * recommend_rate
    returners = customers * return_rate
    wom_entrants = sharers * wom["views_per_share"] * wom["discover_per_view"] + recommenders * wom["referrals_per_recommender"]
    funnel_rate = customers / entrants if entrants else 0.0
    wom_customers = wom_entrants * funnel_rate
    total_customers = customers + wom_customers
    return {
        "entrants": entrants, "funnel": rows, "customers": customers, "sharers": sharers, "recommenders": recommenders,
        "returners": returners, "wom_entrants": wom_entrants, "wom_customers": wom_customers,
        "total_customers": total_customers, "revenue": total_customers * price,
        "future_repeat_revenue": returners * price, "journey_conversion": funnel_rate,
    }


def apply_intervention(stages: list[dict[str, Any]], intervention: dict[str, Any], level: str = "mid") -> list[dict[str, Any]]:
    """Return modified stages. ``level`` picks the low, mid or high effect estimate."""
    out = deepcopy(stages)
    kind = intervention["kind"]
    key = intervention["stage_key"]
    params = intervention.get("params") or {}
    uplift = float(intervention.get(f"uplift_{level}", 0.0))
    stage = next((s for s in out if s["key"] == key), None)
    if stage is None:
        raise ValueError(f"Stage '{key}' is not in this journey.")
    if kind == "reduce_steps":
        steps_now = int(params.get("steps_from") or stage.get("steps") or 5)
        steps_new = int(params.get("steps_to", 2))
        if not 0 < steps_new <= steps_now:
            raise ValueError("New step count must be between 1 and the current number of steps.")
        conv = float(stage.get("conversion", 1.0))
        per_step = conv ** (1 / steps_now)
        theoretical = per_step ** steps_new
        # Step drop-offs are rarely independent; realize only part of the theoretical gain (assumption A23).
        realized = {"low": 0.25, "mid": 0.5, "high": 1.0}[level]
        stage["conversion"] = min(0.999, conv + realized * (theoretical - conv))
        stage["steps"] = steps_new
    elif kind == "conversion_uplift":
        if stage.get("kind") == "outcome":
            stage["rate"] = min(0.999, float(stage.get("rate", 0)) * (1 + uplift))
        else:
            stage["conversion"] = min(0.999, float(stage.get("conversion", 1.0)) * (1 + uplift))
    elif kind == "satisfaction_uplift":
        # A better experience raises the outcome loops: sharing, recommending and returning.
        for s in out:
            if s.get("kind") == "outcome" and s["key"] in ("share", "recommend", "return", "advocacy", "retention"):
                s["rate"] = min(0.999, float(s.get("rate", 0)) * (1 + uplift))
    else:
        raise ValueError(f"Unknown intervention kind '{kind}'.")
    return out


def simulate_intervention(stages: list[dict[str, Any]], intervention: dict[str, Any], entrants: float, price: float,
                          wom: dict[str, float] | None = None) -> dict[str, Any]:
    before = simulate(stages, entrants, price, wom)
    out: dict[str, Any] = {"before": before, "levels": {}}
    for level in ("low", "mid", "high"):
        after = simulate(apply_intervention(stages, intervention, level), entrants, price, wom)
        out["levels"][level] = {
            "after": after,
            "delta_customers": after["total_customers"] - before["total_customers"],
            "delta_revenue": after["revenue"] - before["revenue"],
            "pct_customers": ((after["total_customers"] / before["total_customers"]) - 1) if before["total_customers"] else None,
        }
    out["assumptions"] = [
        "Stage conversion rates are editable assumptions; replace them with analytics data when available.",
        "Effects are estimates to validate with an experiment, not forecasts.",
    ]
    if intervention["kind"] == "reduce_steps":
        out["assumptions"].append("Step reduction assumes partly independent drop-off per step; 25%, 50% and 100% of the "
                                  "theoretical gain define the low, mid and high estimates.")
    return out


def prioritize(pain_points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score = frequency x severity x reach x 100.

    Frequency is the share of reviews that mention the problem, severity is its mean negativity (0 to 1)
    and reach is the share of customers exposed to it (1.0 by default; editable per pain point).
    """
    out = []
    for p in pain_points:
        reach = float(p.get("reach") if p.get("reach") is not None else 1.0)
        score = float(p.get("frequency", 0)) * float(p.get("severity", 0)) * reach * 100
        out.append({**p, "reach": reach, "score": score})
    out.sort(key=lambda x: -x["score"])
    return out


INTERVENTION_LIBRARY = {
    "Complicated booking process": {"kind": "reduce_steps", "title": "Cut booking from five steps to two",
                                    "description": "One page: choose date, pay by QRIS or card, instant e-ticket. No WhatsApp confirmation.",
                                    "params": {"steps_from": 5, "steps_to": 2}, "effort": "M"},
    "Manual transfer and confirmation": {"kind": "reduce_steps", "title": "Replace manual transfer with instant payment",
                                         "description": "Instant QRIS, e-wallet and card payment with automatic confirmation.",
                                         "params": {"steps_from": 5, "steps_to": 3}, "effort": "M"},
    "Online payment errors": {"kind": "conversion_uplift", "title": "Fix payment failures and add a fallback method",
                              "description": "Monitor the payment page and offer a second payment method.",
                              "uplift": (0.05, 0.10, 0.20), "effort": "S"},
    "Missing or outdated information": {"kind": "conversion_uplift", "title": "Publish clear schedules, prices and directions",
                                        "description": "Bilingual page with schedules, prices, map, ferry times and FAQ.",
                                        "uplift": (0.05, 0.12, 0.20), "effort": "S"},
    "Ferry schedule and waiting": {"kind": "conversion_uplift", "title": "Live ferry times and a bundled shuttle",
                                   "description": "Share live ferry times and offer a shuttle from Parapat timed to the ferry.",
                                   "uplift": (0.01, 0.02, 0.03), "effort": "L"},
    "Road access and traffic": {"kind": "conversion_uplift", "title": "Set expectations on travel time and offer pickup",
                                "description": "Show realistic travel times and offer hotel pickup packages.",
                                "uplift": (0.005, 0.01, 0.02), "effort": "M"},
    "Weak storytelling at the start": {"kind": "satisfaction_uplift", "title": "Redesign the first 15 minutes around local storytelling",
                                       "description": "A local storyteller welcomes guests with the story of the village, ulos and tortor "
                                                      "before the tour starts.",
                                       "uplift": (0.10, 0.20, 0.35), "effort": "S"},
    "Price concerns": {"kind": "conversion_uplift", "title": "Add a family bundle and clarify what the price includes",
                       "description": "Show inclusions (guide, performance, snack) and offer a family package.",
                       "uplift": (0.03, 0.07, 0.12), "effort": "S"},
}


def propose_intervention(pain_point: dict[str, Any]) -> dict[str, Any] | None:
    spec = INTERVENTION_LIBRARY.get(pain_point.get("theme", ""))
    if not spec:
        return None
    low, mid, high = spec.get("uplift", (0.0, 0.0, 0.0))
    return {"stage_key": pain_point["stage"], "title": spec["title"], "description": spec["description"], "kind": spec["kind"],
            "params": spec.get("params", {}), "uplift_low": low, "uplift_mid": mid, "uplift_high": high,
            "effort": spec.get("effort", "M"), "confidence": "low"}


def experiment_for(intervention: dict[str, Any], stages: list[dict[str, Any]], entrants: float,
                   alpha: float = 0.05, power: float = 0.8) -> dict[str, Any]:
    stage = next(s for s in stages if s["key"] == intervention["stage_key"])
    is_outcome = stage.get("kind") == "outcome"
    if intervention["kind"] == "satisfaction_uplift":
        target_stage = next((s for s in stages if s["key"] in ("recommend", "advocacy")), stage)
        baseline = float(target_stage.get("rate", 0.3))
        metric = f"{target_stage['name']} rate (share of guests who recommend)"
        low = float(intervention.get("uplift_low") or 0.1)
    elif intervention["kind"] == "reduce_steps":
        baseline = float(stage.get("conversion", 0.4))
        after_low = apply_intervention(stages, intervention, "low")
        low = next(s for s in after_low if s["key"] == stage["key"])["conversion"] / baseline - 1
        metric = f"{stage['name']} completion rate"
    else:
        baseline = float(stage.get("rate" if is_outcome else "conversion", 0.3))
        low = float(intervention.get("uplift_low") or 0.05)
        metric = f"{stage['name']} {'rate' if is_outcome else 'conversion rate'}"
    mde = max(0.05, round(low, 3))
    if baseline * (1 + mde) >= 1:
        mde = round((0.99 / baseline) - 1, 3)
    size = ab_sample_size(baseline, mde, alpha, power)
    reach = entrants
    for s in stages:
        if s["key"] == stage["key"]:
            break
        if s.get("kind", "funnel") == "funnel":
            reach *= float(s.get("conversion", 1.0))
    daily = max(1, int(reach / 30))
    duration = int(math.ceil(2 * size["n_per_arm"] / daily))
    fmt = ".1%" if baseline >= 0.9 else ".0%"
    notes = []
    if duration > 90:
        notes.append(f"At current traffic this test needs about {duration} days. Consider an earlier, more frequent metric "
                     "(for example a post-visit satisfaction score) or accept a larger minimum detectable effect.")
    return {
        "name": f"Test: {intervention['title']}",
        "hypothesis": (f"If we {intervention['title'][0].lower() + intervention['title'][1:]}, the {metric.lower()} will rise from "
                       f"{baseline:{fmt}} to at least {baseline * (1 + mde):{fmt}}."),
        "notes": notes,
        "primary_metric": metric, "baseline_rate": baseline, "mde": mde, "alpha": alpha, "power": power,
        "sample_size_per_arm": size["n_per_arm"], "expected_daily_traffic": daily,
        "duration_days": duration,
        "variants": [{"name": "Control", "description": "Current experience"},
                     {"name": "Treatment", "description": intervention.get("description") or intervention["title"]}],
    }
