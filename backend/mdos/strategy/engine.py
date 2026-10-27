"""Simulation engine: Budget -> Reach -> Engagement -> Leads -> Conversion -> Revenue -> Profit.

Building blocks (documented in docs/17-methods-reference.md):
* Reach saturates with a Poisson exposure model: reach = N * (1 - exp(-impressions / N)).
* Each channel's audience is split across segments by segment share times channel affinity.
* Conversion at a price other than the reference price scales with the segment's price response:
  a research demand curve (Gabor-Granger points, shifted by the segment's WTP multiplier) or a
  constant elasticity.
* Competitor price changes scale conversion with a cross-price elasticity.
* Word of mouth adds one generation of referred customers (conservative, no infinite loop).
"""

from __future__ import annotations

import copy
import math
from typing import Any

import numpy as np

from .model import MarketModel


def _interp_share(points: list[tuple[float, float]], price: float) -> float:
    prices = [p for p, _ in points]
    shares = [s for _, s in points]
    if price <= prices[0]:
        # Below the tested range, extend the first segment's slope, capped at 100%.
        (p1, s1), (p2, s2) = points[0], points[1]
        slope = (s2 - s1) / (p2 - p1) if p2 != p1 else 0.0
        return min(1.0, max(0.0, s1 + slope * (price - p1)))
    if price >= prices[-1]:
        # Beyond the tested range, continue the last segment's slope but never below zero.
        (p1, s1), (p2, s2) = points[-2], points[-1]
        slope = (s2 - s1) / (p2 - p1) if p2 != p1 else 0.0
        return max(0.0, s2 + slope * (price - p2))
    return float(np.interp(price, prices, shares))


def price_multiplier(model: MarketModel, segment_index: int, price: float) -> float:
    seg = model.segments[segment_index]
    ref = model.offer.reference_price
    if model.price_response.mode == "curve":
        pts = sorted((p.price, p.share) for p in model.price_response.points)
        base = _interp_share(pts, ref / seg.wtp_multiplier)
        now = _interp_share(pts, price / seg.wtp_multiplier)
        return (now / base) if base > 0 else 0.0
    return (price / ref) ** seg.price_elasticity


def competitor_multiplier(model: MarketModel, segment_index: int) -> float:
    seg = model.segments[segment_index]
    factor = 1.0
    for comp in model.competitors:
        base = comp.base_price or comp.price
        if base > 0 and comp.price > 0:
            factor *= (comp.price / base) ** seg.cross_price_elasticity
    return factor


def simulate(model: MarketModel) -> dict[str, Any]:
    offer = model.offer
    price = offer.price
    seg_count = len(model.segments)
    channel_rows = []
    seg_customers = np.zeros(seg_count)
    seg_reach = np.zeros(seg_count)
    price_mult = [price_multiplier(model, i, price) for i in range(seg_count)]
    comp_mult = [competitor_multiplier(model, i) for i in range(seg_count)]
    totals = {"spend": 0.0, "impressions": 0.0, "reach": 0.0, "engaged": 0.0, "leads": 0.0, "customers": 0.0, "commission": 0.0}

    for ch in model.channels:
        impressions = (ch.budget / ch.cpm * 1000 if ch.cpm > 0 else 0.0) + ch.organic_impressions
        reach = ch.audience_size * (1 - math.exp(-impressions / ch.audience_size)) if impressions > 0 else 0.0
        raw = [s.share * ch.affinity.get(s.key, 1.0) for s in model.segments]
        total_w = sum(raw)
        weights = [w / total_w for w in raw] if total_w > 0 else [1 / seg_count] * seg_count
        engaged_total = leads_total = customers_total = 0.0
        for i, seg in enumerate(model.segments):
            r = reach * weights[i]
            engaged = r * ch.engagement_rate
            leads = engaged * ch.lead_rate
            conv_rate = min(1.0, ch.conversion_rate * seg.conversion_multiplier * price_mult[i] * comp_mult[i])
            customers = leads * conv_rate
            seg_reach[i] += r
            seg_customers[i] += customers
            engaged_total += engaged
            leads_total += leads
            customers_total += customers
        commission = customers_total * price * ch.commission_rate
        channel_rows.append({"key": ch.key, "name": ch.name, "spend": ch.budget, "impressions": impressions, "reach": reach,
                             "engaged": engaged_total, "leads": leads_total, "customers": customers_total,
                             "commission": commission})
        totals["spend"] += ch.budget
        totals["impressions"] += impressions
        totals["reach"] += reach
        totals["engaged"] += engaged_total
        totals["leads"] += leads_total
        totals["customers"] += customers_total
        totals["commission"] += commission

    paid_customers = totals["customers"]
    referrals = paid_customers * model.word_of_mouth_rate
    customers = paid_customers + referrals
    capped = False
    if offer.capacity is not None and customers > offer.capacity:
        scale = offer.capacity / customers
        customers, paid_customers, referrals = offer.capacity, paid_customers * scale, referrals * scale
        seg_customers *= scale
        capped = True
    seg_customers_total = seg_customers * (1 + model.word_of_mouth_rate)
    revenue = customers * price
    unit_margin = price - offer.unit_cost
    gross_margin = customers * unit_margin - totals["commission"]
    profit = gross_margin - totals["spend"] - offer.fixed_costs
    romi = (gross_margin - totals["spend"]) / totals["spend"] if totals["spend"] > 0 else None
    cac = totals["spend"] / paid_customers if paid_customers > 0 else None
    effective_margin = unit_margin - price * _avg_commission(model, channel_rows, paid_customers)
    break_even_customers = (offer.fixed_costs + totals["spend"]) / effective_margin if effective_margin > 0 else None

    clv_rows = []
    for i, seg in enumerate(model.segments):
        r, d = seg.repeat_rate, model.discount_rate
        clv = unit_margin + unit_margin * r / (1 + d - r)
        clv_rows.append({"key": seg.key, "name": seg.name, "customers": float(seg_customers_total[i]),
                         "share_of_customers": float(seg_customers_total[i] / customers) if customers > 0 else 0.0,
                         "revenue": float(seg_customers_total[i] * price), "reach": float(seg_reach[i]),
                         "reach_to_customer": float(seg_customers[i] / seg_reach[i]) if seg_reach[i] > 0 else 0.0,
                         "price_multiplier": price_mult[i], "competitor_multiplier": comp_mult[i], "clv": clv})
    clv_avg = (sum(r["clv"] * r["customers"] for r in clv_rows) / customers) if customers > 0 else None

    for row in channel_rows:
        row["cac"] = row["spend"] / row["customers"] if row["customers"] > 0 and row["spend"] > 0 else None
        row["revenue"] = row["customers"] * price
        margin = row["customers"] * unit_margin - row["commission"]
        row["romi"] = (margin - row["spend"]) / row["spend"] if row["spend"] > 0 else None

    kpis = {
        "price": price, "spend": totals["spend"], "impressions": totals["impressions"], "reach": totals["reach"],
        "engaged": totals["engaged"], "leads": totals["leads"], "paid_customers": paid_customers, "referrals": referrals,
        "customers": customers, "revenue": revenue, "gross_margin": gross_margin, "commission": totals["commission"],
        "fixed_costs": offer.fixed_costs, "profit": profit, "romi": romi, "cac": cac, "clv": clv_avg,
        "clv_to_cac": (clv_avg / cac) if (clv_avg and cac) else None, "break_even_customers": break_even_customers,
        "capacity_limited": capped, "market_penetration": customers / model.market_size,
    }
    funnel = [
        {"stage": "Budget", "value": totals["spend"], "unit": model.currency},
        {"stage": "Reach", "value": totals["reach"], "unit": "people"},
        {"stage": "Engagement", "value": totals["engaged"], "unit": "people"},
        {"stage": "Leads", "value": totals["leads"], "unit": "people"},
        {"stage": "Conversion", "value": customers, "unit": "customers"},
        {"stage": "Revenue", "value": revenue, "unit": model.currency},
        {"stage": "Profit", "value": profit, "unit": model.currency},
    ]
    return {"kpis": kpis, "funnel": funnel, "channels": channel_rows, "segments": clv_rows, "currency": model.currency,
            "period": model.period}


def _avg_commission(model: MarketModel, rows: list[dict], paid_customers: float) -> float:
    if paid_customers <= 0:
        return 0.0
    rates = {c.key: c.commission_rate for c in model.channels}
    return sum(r["customers"] * rates[r["key"]] for r in rows) / paid_customers


# ----------------------------------------------------------------------------------------------
# Levers (scenario definitions)
# ----------------------------------------------------------------------------------------------

LEVER_TYPES = {"set_price", "reallocate_budget", "set_budget", "scale_budget", "set_segment_share", "competitor_price",
               "competitor_price_change", "set_param", "conversion_uplift", "set_wom"}


def _find(items: list, key: str, kind: str):
    for item in items:
        if item.key == key:
            return item
    raise ValueError(f"Unknown {kind} '{key}'.")


def describe_lever(lever: dict[str, Any], model: MarketModel) -> str:
    t = lever.get("type")
    cur = model.currency
    money = (lambda v: "Rp " + f"{v:,.0f}".replace(",", ".")) if cur == "IDR" else (lambda v: f"{cur} {v:,.2f}")
    if t == "set_price":
        return f"Price {money(model.offer.price)} to {money(lever['value'])}"
    if t == "reallocate_budget":
        a = _find(model.channels, lever["from"], "channel").name
        b = _find(model.channels, lever["to"], "channel").name
        return f"Move {lever['share']:.0%} of {a} budget to {b}"
    if t == "set_budget":
        return f"{_find(model.channels, lever['channel'], 'channel').name} budget to {money(lever['value'])}"
    if t == "scale_budget":
        return f"Scale all budgets by {lever['factor']:.2f}x"
    if t == "set_segment_share":
        return f"{_find(model.segments, lever['segment'], 'segment').name} becomes {lever['value']:.0%} of the market"
    if t == "competitor_price":
        return f"{_find(model.competitors, lever['competitor'], 'competitor').name} price to {money(lever['value'])}"
    if t == "competitor_price_change":
        return f"{_find(model.competitors, lever['competitor'], 'competitor').name} changes price by {lever['pct']:+.0%}"
    if t == "conversion_uplift":
        return f"Conversion rates {lever['pct']:+.0%}" + (f" on {lever['channel']}" if lever.get("channel") else "")
    if t == "set_wom":
        return f"Word-of-mouth rate to {lever['value']:.2f}"
    if t == "set_param":
        return f"{lever['path']} = {lever['value']}"
    return str(lever)


def apply_levers(model: MarketModel, levers: list[dict[str, Any]]) -> MarketModel:
    data = copy.deepcopy(model.model_dump())
    m = MarketModel.model_validate(data)
    for lever in levers:
        t = lever.get("type")
        if t not in LEVER_TYPES:
            raise ValueError(f"Unknown lever type '{t}'.")
        if t == "set_price":
            m.offer.price = float(lever["value"])
        elif t == "reallocate_budget":
            src = _find(m.channels, lever["from"], "channel")
            dst = _find(m.channels, lever["to"], "channel")
            moved = src.budget * float(lever["share"])
            src.budget -= moved
            dst.budget += moved
        elif t == "set_budget":
            _find(m.channels, lever["channel"], "channel").budget = float(lever["value"])
        elif t == "scale_budget":
            for ch in m.channels:
                ch.budget *= float(lever["factor"])
        elif t == "set_segment_share":
            target = _find(m.segments, lever["segment"], "segment")
            value = float(lever["value"])
            if not 0 <= value <= 1:
                raise ValueError("Segment share must be between 0 and 1.")
            others = [s for s in m.segments if s.key != target.key]
            rest = sum(s.share for s in others)
            for s in others:
                s.share = (s.share / rest) * (1 - value) if rest > 0 else (1 - value) / len(others)
            target.share = value
        elif t == "competitor_price":
            comp = _find(m.competitors, lever["competitor"], "competitor")
            comp.base_price = comp.base_price or comp.price
            comp.price = float(lever["value"])
        elif t == "competitor_price_change":
            comp = _find(m.competitors, lever["competitor"], "competitor")
            comp.base_price = comp.base_price or comp.price
            comp.price = comp.price * (1 + float(lever["pct"]))
        elif t == "conversion_uplift":
            for ch in m.channels:
                if not lever.get("channel") or ch.key == lever["channel"]:
                    ch.conversion_rate = min(1.0, ch.conversion_rate * (1 + float(lever["pct"])))
        elif t == "set_wom":
            m.word_of_mouth_rate = float(lever["value"])
        elif t == "set_param":
            _set_path(m, lever["path"], float(lever["value"]))
    return MarketModel.model_validate(m.model_dump())


def _set_path(m: MarketModel, path: str, value: float) -> None:
    parts = path.split(".")
    if parts[0] == "offer" and len(parts) == 2:
        setattr(m.offer, parts[1], value)
    elif parts[0] in ("channels", "segments", "competitors") and len(parts) == 3:
        setattr(_find(getattr(m, parts[0]), parts[1], parts[0][:-1]), parts[2], value)
    elif len(parts) == 1 and hasattr(m, parts[0]):
        setattr(m, parts[0], value)
    else:
        raise ValueError(f"Unknown parameter path '{path}'.")
