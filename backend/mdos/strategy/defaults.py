"""Build a baseline market model from research evidence plus clearly labeled placeholder assumptions.

The Market Model agent uses this deterministic builder. Wherever research evidence exists (price
response curve, willingness to pay by group, sample composition) it is used and cited; everything else
is a placeholder with low confidence that the user is asked to replace.
"""

from __future__ import annotations

from typing import Any

from ..research.design import nice_price
from .model import Assumption, Channel, Competitor, MarketModel, Offer, PricePoint, PriceResponse, Segment

FX_FROM_IDR = {"IDR": 1.0, "USD": 1 / 16000, "EUR": 1 / 17500, "SGD": 1 / 12000, "MYR": 1 / 3500}


def _curve_share(points: list[dict[str, float]], price: float) -> float:
    from .engine import _interp_share

    return _interp_share(sorted((p["price"], p["share"]) for p in points), price)


def wtp_multiplier_for(points: list[dict[str, float]], target: float, group_share: float) -> float:
    """Find m so that the curve evaluated at target/m equals the group's observed share (bisection)."""
    lo, hi = 0.3, 3.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if _curve_share(points, target / mid) < group_share:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 3)


def default_model(*, name: str, offering: str, currency: str = "IDR", tourism: bool = True,
                  inputs: dict[str, Any] | None = None) -> MarketModel:
    inputs = inputs or {}
    fx = FX_FROM_IDR.get(currency, 1.0)
    target = inputs.get("target_price") or (inputs.get("vw_range") or {}).get("opp") or (150_000 * fx)
    baseline_price = inputs.get("baseline_price") or (round(target * 1.2 / (10_000 * fx)) * 10_000 * fx
                                                      if inputs.get("target_price") else target)
    points = inputs.get("price_points") or []
    assumptions: list[Assumption] = []

    # Price response ------------------------------------------------------------------------------
    if len(points) >= 2:
        price_response = PriceResponse(mode="curve", points=[PricePoint(**p) for p in points],
                                       evidence_id=inputs.get("price_points_evidence_id"))
        assumptions.append(Assumption(key="price_response", label="Price response curve (Gabor-Granger)",
                                      value=f"{len(points)} tested prices", source="evidence",
                                      evidence_id=inputs.get("price_points_evidence_id"), confidence="medium",
                                      note="Stated intent; real demand is usually lower."))
    else:
        price_response = PriceResponse(mode="elasticity")
        assumptions.append(Assumption(key="price_response", label="Price elasticity", value=-1.2, source="guess",
                                      confidence="low", note="Run a Gabor-Granger analysis to replace this."))

    # Segments ------------------------------------------------------------------------------------
    group_shares = inputs.get("group_shares") or {}
    wtp_groups = {g["group"].lower(): g for g in inputs.get("wtp_by_group", [])}
    if tourism:
        intl_share = float(group_shares.get("International", 0.35))
        genz_share = float(inputs.get("genz_share", 0.24)) * (1 - intl_share)
        domestic_share = 1 - intl_share - genz_share
        dom_mult = intl_mult = 1.0
        if len(points) >= 2 and inputs.get("target_price"):
            if "domestic" in wtp_groups:
                dom_mult = wtp_multiplier_for(points, inputs["target_price"], wtp_groups["domestic"]["share"])
            if "international" in wtp_groups:
                intl_mult = wtp_multiplier_for(points, inputs["target_price"], wtp_groups["international"]["share"])
        segments = [
            Segment(key="gen_z", name="Domestic Gen Z (18-24)", share=round(genz_share, 3), cross_price_elasticity=0.7,
                    wtp_multiplier=round(dom_mult * 0.9, 3), repeat_rate=0.03, conversion_multiplier=0.9,
                    needs=["Shareable moments", "Affordable price", "Fun with friends"]),
            Segment(key="domestic", name="Domestic adults and families", share=round(domestic_share, 3),
                    cross_price_elasticity=0.6, wtp_multiplier=dom_mult, repeat_rate=0.03,
                    needs=["Family-friendly", "Value for money", "Easy access"]),
            Segment(key="international", name="International visitors", share=round(intl_share, 3), cross_price_elasticity=0.2,
                    wtp_multiplier=intl_mult, repeat_rate=0.01, conversion_multiplier=1.1,
                    needs=["Authentic culture", "English-speaking guide", "Easy online booking"]),
        ]
        wtp_ev = inputs.get("wtp_by_group_evidence_id")
        assumptions += [
            Assumption(key="segments", label="Segment shares", value="Gen Z / domestic / international",
                       source="evidence" if group_shares else "guess", evidence_id=inputs.get("group_shares_evidence_id"),
                       confidence="medium" if group_shares else "low",
                       note="From the survey sample composition; check against official visitor statistics."),
            Assumption(key="segments.domestic.wtp_multiplier", label="Domestic WTP multiplier", value=dom_mult,
                       source="evidence" if wtp_ev else "guess", evidence_id=wtp_ev, confidence="medium" if wtp_ev else "low"),
            Assumption(key="segments.international.wtp_multiplier", label="International WTP multiplier", value=intl_mult,
                       source="evidence" if wtp_ev else "guess", evidence_id=wtp_ev, confidence="medium" if wtp_ev else "low"),
            Assumption(key="segments.gen_z.wtp_multiplier", label="Gen Z WTP multiplier", value=round(dom_mult * 0.9, 3),
                       source="expert_judgment", confidence="low", note="Assumed 10% below domestic adults."),
            Assumption(key="segments.gen_z.cross_price_elasticity", label="Gen Z sensitivity to competitor prices", value=0.7,
                       source="guess", confidence="low"),
        ]
    else:
        segments = [
            Segment(key="core", name="Core customers", share=0.6, repeat_rate=0.2),
            Segment(key="occasional", name="Occasional customers", share=0.4, repeat_rate=0.08, conversion_multiplier=0.8),
        ]
        assumptions.append(Assumption(key="segments", label="Segment shares", value="60% / 40%", source="guess", confidence="low"))

    # Market and channels (placeholders, benchmark-style values in IDR converted to the currency) ---
    market_size = float(inputs.get("market_size") or 60_000)
    assumptions.append(Assumption(key="market_size", label="Addressable visitors per month", value=market_size, unit="people",
                                  source="guess", confidence="low",
                                  note="Replace with official statistics (for example BPS or the regional tourism office)."))
    channels = [
        Channel(key="instagram", name="Instagram", budget=15_000_000 * fx, cpm=25_000 * fx, audience_size=market_size * 20,
                engagement_rate=0.025, lead_rate=0.15, conversion_rate=0.08,
                affinity={"gen_z": 1.5, "domestic": 1.0, "international": 0.8}),
        Channel(key="tiktok", name="TikTok", budget=10_000_000 * fx, cpm=15_000 * fx, audience_size=market_size * 25,
                engagement_rate=0.035, lead_rate=0.10, conversion_rate=0.06,
                affinity={"gen_z": 3.0, "domestic": 0.9, "international": 0.4}),
        Channel(key="google", name="Google Search", budget=8_000_000 * fx, cpm=60_000 * fx, audience_size=market_size * 2,
                engagement_rate=0.08, lead_rate=0.25, conversion_rate=0.12,
                affinity={"gen_z": 0.6, "domestic": 1.0, "international": 2.0}),
        Channel(key="ota", name="Online travel agents", budget=0, cpm=0, audience_size=market_size * 1.5,
                organic_impressions=market_size * 1.5, engagement_rate=0.10, lead_rate=0.30, conversion_rate=0.15,
                commission_rate=0.18, affinity={"gen_z": 0.5, "domestic": 0.9, "international": 2.5}),
    ]
    if not tourism:
        channels = [c for c in channels if c.key != "ota"]
    for ch in channels:
        assumptions.append(Assumption(key=f"channels.{ch.key}", label=f"{ch.name} funnel rates and costs", source="benchmark",
                                      confidence="low", note="Calibrate with your own campaign data."))
    competitors = []
    if tourism:
        competitors.append(Competitor(key="village_tour", name="Existing village tour", price=nice_price(target * 0.8),
                                      attributes={"Authenticity": 3.0}))
        assumptions.append(Assumption(key="competitors.village_tour", label="Competitor price", value=nice_price(target * 0.8),
                                      source="guess", confidence="low", note="Check current market prices."))
    offer = Offer(name=offering[:1].upper() + offering[1:] if offering else name, price=float(baseline_price),
                  reference_price=float(target), unit_cost=float(nice_price(target * 0.35)),
                  fixed_costs=float(25_000_000 * fx), attributes={"Authenticity": float(inputs.get("authenticity", 4.0))})
    assumptions += [
        Assumption(key="offer.unit_cost", label="Variable cost per customer", value=offer.unit_cost, source="expert_judgment",
                   confidence="medium", note="Guide, performers, materials and snack."),
        Assumption(key="offer.fixed_costs", label="Fixed costs per month", value=offer.fixed_costs, source="expert_judgment",
                   confidence="medium", note="Staff, venue, permits."),
        Assumption(key="word_of_mouth_rate", label="Referred customers per customer", value=0.15, source="guess", confidence="low"),
    ]
    if inputs.get("vw_range"):
        assumptions.append(Assumption(key="offer.price", label="Acceptable price range (Van Westendorp)",
                                      value=f"{inputs['vw_range'].get('pmc'):.0f} to {inputs['vw_range'].get('pme'):.0f}",
                                      source="evidence", evidence_id=inputs.get("vw_evidence_id"), confidence="medium"))
    return MarketModel(currency=currency, market_name=name, market_size=market_size, segments=segments, channels=channels,
                       competitors=competitors, offer=offer, price_response=price_response, word_of_mouth_rate=0.15,
                       assumptions=assumptions)


def graph1_scenarios(model: MarketModel, target_price: float | None) -> list[dict[str, Any]]:
    """The four what-if questions from the founder vision notes, adapted to the model's keys."""
    scenarios = []
    if target_price and abs(target_price - model.offer.price) > 1e-6:
        scenarios.append({"name": "Lower the price to the tested target", "levers": [{"type": "set_price", "value": target_price}]})
    keys = {c.key for c in model.channels}
    if {"instagram", "tiktok"} <= keys:
        scenarios.append({"name": "Move 30% of the Instagram budget to TikTok",
                          "levers": [{"type": "reallocate_budget", "from": "instagram", "to": "tiktok", "share": 0.3}]})
    if any(s.key == "gen_z" for s in model.segments):
        scenarios.append({"name": "Gen Z becomes 40% of the market", "levers": [{"type": "set_segment_share", "segment": "gen_z", "value": 0.4}]})
    if model.competitors:
        scenarios.append({"name": f"{model.competitors[0].name} cuts its price by 25%",
                          "levers": [{"type": "competitor_price_change", "competitor": model.competitors[0].key, "pct": -0.25}]})
    return scenarios
