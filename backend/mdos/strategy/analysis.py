"""Scenario comparison, waterfall, tornado sensitivity, Monte Carlo, price curve and media optimizer."""

from __future__ import annotations

import copy
import math
from typing import Any

import numpy as np

from .engine import apply_levers, describe_lever, simulate
from .model import MarketModel

KPI_KEYS = ("revenue", "profit", "customers", "spend", "romi", "cac", "clv", "gross_margin", "reach", "leads")
SPREAD = {"low": 0.35, "medium": 0.20, "high": 0.10}


def compare(base: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k in KPI_KEYS:
        a, b = base["kpis"].get(k), scenario["kpis"].get(k)
        if isinstance(a, int | float) and isinstance(b, int | float):
            out[k] = {"baseline": a, "scenario": b, "delta": b - a, "pct": ((b - a) / abs(a)) if a else None}
    return out


def waterfall(model: MarketModel, levers: list[dict[str, Any]], metric: str = "profit") -> list[dict[str, Any]]:
    """Profit bridge from baseline to scenario, applying levers in the listed order (order matters)."""
    steps = []
    current = model
    value = simulate(model)["kpis"][metric]
    steps.append({"label": "Baseline", "value": value, "type": "total"})
    applied: list[dict[str, Any]] = []
    for lever in levers:
        applied.append(lever)
        nxt = apply_levers(model, applied)
        new_value = simulate(nxt)["kpis"][metric]
        steps.append({"label": describe_lever(lever, current), "delta": new_value - value, "type": "delta"})
        value, current = new_value, nxt
    steps.append({"label": "Scenario", "value": value, "type": "total"})
    return steps


def parameters(model: MarketModel) -> list[tuple[str, str, float]]:
    """(path, label, value) for every numeric assumption that sensitivity analysis can vary."""
    params = [("offer.price", "Price", model.offer.price), ("offer.unit_cost", "Unit cost", model.offer.unit_cost),
              ("offer.fixed_costs", "Fixed costs", model.offer.fixed_costs), ("market_size", "Market size", model.market_size)]
    if model.word_of_mouth_rate > 0:
        params.append(("word_of_mouth_rate", "Word-of-mouth rate", model.word_of_mouth_rate))
    for ch in model.channels:
        for attr, label in (("budget", "budget"), ("cpm", "CPM"), ("engagement_rate", "engagement rate"),
                            ("lead_rate", "lead rate"), ("conversion_rate", "conversion rate"), ("audience_size", "audience size")):
            value = getattr(ch, attr)
            if value > 0:
                params.append((f"channels.{ch.key}.{attr}", f"{ch.name} {label}", value))
    for seg in model.segments:
        if model.price_response.mode == "curve":
            params.append((f"segments.{seg.key}.wtp_multiplier", f"{seg.name} WTP multiplier", seg.wtp_multiplier))
        else:
            params.append((f"segments.{seg.key}.price_elasticity", f"{seg.name} price elasticity", seg.price_elasticity))
    return params


def _with_param(model: MarketModel, path: str, value: float) -> MarketModel:
    if path == "market_size":
        data = copy.deepcopy(model.model_dump())
        data["market_size"] = value
        return MarketModel.model_validate(data)
    lever = {"type": "set_param", "path": path, "value": value}
    return apply_levers(model, [lever])


def sensitivity(model: MarketModel, metric: str = "profit", pct: float = 0.2, top: int = 12) -> dict[str, Any]:
    base = simulate(model)["kpis"][metric]
    rows = []
    for path, label, value in parameters(model):
        if path == "market_size":
            continue  # market size only matters through audience sizes in this model
        lo_v, hi_v = value * (1 - pct), value * (1 + pct)
        if path.endswith(("_rate", "rate")) and not path.endswith("price_elasticity"):
            hi_v = min(hi_v, 0.999)
        try:
            lo = simulate(_with_param(model, path, lo_v))["kpis"][metric]
            hi = simulate(_with_param(model, path, hi_v))["kpis"][metric]
        except ValueError:
            continue
        rows.append({"parameter": path, "label": label, "base_value": value, "low_value": lo_v, "high_value": hi_v,
                     "low": lo, "high": hi, "swing": abs(hi - lo)})
    rows.sort(key=lambda r: -r["swing"])
    return {"metric": metric, "base": base, "pct": pct, "rows": rows[:top]}


def _confidence_for(model: MarketModel, path: str) -> str:
    for a in model.assumptions:
        if a.key == path or path.startswith(a.key + "."):
            return a.confidence
    return "medium"


def monte_carlo(model: MarketModel, n: int = 1000, seed: int = 7) -> dict[str, Any]:
    """Vary every assumption with a log-normal spread set by its confidence; report P10, P50 and P90."""
    rng = np.random.default_rng(seed)
    n = int(min(max(n, 200), 5000))
    params = [(p, lab, v) for p, lab, v in parameters(model) if p not in ("offer.price", "market_size")]
    metrics = {"profit": [], "revenue": [], "customers": []}
    for _ in range(n):
        m = copy.deepcopy(model.model_dump())
        for path, _label, value in params:
            sigma = SPREAD[_confidence_for(model, path)]
            factor = math.exp(rng.normal(0, sigma))
            new = value * factor
            if path.endswith(("engagement_rate", "lead_rate", "conversion_rate", "word_of_mouth_rate")):
                new = min(new, 0.95)
            _assign(m, path, new)
        try:
            k = simulate(MarketModel.model_validate(m))["kpis"]
        except ValueError:
            continue
        for key in metrics:
            metrics[key].append(k[key])
    out: dict[str, Any] = {"runs": len(metrics["profit"]), "seed": seed}
    for key, values in metrics.items():
        arr = np.array(values)
        out[key] = {"p10": float(np.percentile(arr, 10)), "p50": float(np.percentile(arr, 50)),
                    "p90": float(np.percentile(arr, 90)), "mean": float(arr.mean())}
    profits = np.array(metrics["profit"])
    out["probability_profit_positive"] = float((profits > 0).mean())
    hist, edges = np.histogram(profits, bins=24)
    out["profit_histogram"] = [{"x0": float(edges[i]), "x1": float(edges[i + 1]), "count": int(hist[i])} for i in range(len(hist))]
    return out


def _assign(data: dict, path: str, value: float) -> None:
    parts = path.split(".")
    if parts[0] in ("channels", "segments", "competitors"):
        for item in data[parts[0]]:
            if item["key"] == parts[1]:
                item[parts[2]] = value
    elif parts[0] == "offer":
        data["offer"][parts[1]] = value
    else:
        data[parts[0]] = value


def price_curve(model: MarketModel, low: float | None = None, high: float | None = None, steps: int = 25) -> dict[str, Any]:
    ref = model.offer.reference_price
    low = low or ref * 0.5
    high = high or ref * 1.6
    rows = []
    for price in np.linspace(low, high, steps):
        k = simulate(apply_levers(model, [{"type": "set_price", "value": float(price)}]))["kpis"]
        rows.append({"price": float(price), "customers": k["customers"], "revenue": k["revenue"], "profit": k["profit"]})
    best_rev = max(rows, key=lambda r: r["revenue"])
    best_profit = max(rows, key=lambda r: r["profit"])
    return {"points": rows, "revenue_max_price": best_rev["price"], "profit_max_price": best_profit["price"],
            "current_price": model.offer.price}


def break_even_price(model: MarketModel) -> float | None:
    """Lowest price (between unit cost and 3x reference) at which profit reaches zero, if any."""
    lo, hi = max(model.offer.unit_cost * 1.01, 1.0), model.offer.reference_price * 3
    grid = np.linspace(lo, hi, 60)
    profits = [simulate(apply_levers(model, [{"type": "set_price", "value": float(p)}]))["kpis"]["profit"] for p in grid]
    for i in range(1, len(grid)):
        if profits[i - 1] < 0 <= profits[i]:
            a, b = grid[i - 1], grid[i]
            for _ in range(30):
                mid = (a + b) / 2
                if simulate(apply_levers(model, [{"type": "set_price", "value": float(mid)}]))["kpis"]["profit"] < 0:
                    a = mid
                else:
                    b = mid
            return float(b)
    return None


def optimize_media(model: MarketModel, total_budget: float | None = None, increments: int = 40,
                   metric: str = "profit") -> dict[str, Any]:
    """Greedy allocation: give each budget increment to the channel with the best marginal gain."""
    paid = [c for c in model.channels if c.cpm > 0]
    if not paid:
        return {"allocation": [], "note": "No paid channels to optimize."}
    total = total_budget if total_budget is not None else sum(c.budget for c in paid)
    step = total / increments
    alloc = {c.key: 0.0 for c in paid}

    def value_for(allocation: dict[str, float]) -> float:
        levers = [{"type": "set_budget", "channel": k, "value": v} for k, v in allocation.items()]
        return simulate(apply_levers(model, levers))["kpis"][metric]

    current = value_for(alloc)
    for _ in range(increments):
        best_key, best_value = None, None
        for key in alloc:
            trial = dict(alloc)
            trial[key] += step
            v = value_for(trial)
            if best_value is None or v > best_value:
                best_key, best_value = key, v
        alloc[best_key] += step
        current = best_value
    baseline = simulate(model)["kpis"][metric]
    names = {c.key: c.name for c in paid}
    return {
        "metric": metric, "total_budget": total,
        "allocation": [{"key": k, "name": names[k], "current": next(c.budget for c in paid if c.key == k), "optimized": v}
                       for k, v in alloc.items()],
        "baseline_value": baseline, "optimized_value": current,
        "levers": [{"type": "set_budget", "channel": k, "value": v} for k, v in alloc.items()],
        "note": "Greedy marginal allocation under the model's saturation curves; treat as a starting point, not an answer.",
    }


def positioning_map(model: MarketModel) -> dict[str, Any]:
    axes = model.positioning_axes[:2] if len(model.positioning_axes) >= 2 else ["Price", "Quality"]
    points = [{"name": model.offer.name, "self": True,
               "x": model.offer.price if axes[0] == "Price" else model.offer.attributes.get(axes[0]),
               "y": model.offer.attributes.get(axes[1])}]
    for comp in model.competitors:
        points.append({"name": comp.name, "self": False,
                       "x": comp.price if axes[0] == "Price" else comp.attributes.get(axes[0]),
                       "y": comp.attributes.get(axes[1])})
    return {"axes": axes, "points": points}
