"""Strategy engine math and API behavior."""

from __future__ import annotations

import math

import pytest

from mdos.strategy import analysis
from mdos.strategy.defaults import default_model, graph1_scenarios, wtp_multiplier_for
from mdos.strategy.engine import apply_levers, simulate
from mdos.strategy.model import Channel, MarketModel, Offer, Segment

POINTS = [{"price": 100000, "share": 0.83}, {"price": 125000, "share": 0.69}, {"price": 150000, "share": 0.61},
          {"price": 175000, "share": 0.52}, {"price": 200000, "share": 0.39}]


def tiny_model(**offer_overrides) -> MarketModel:
    offer = {"name": "Tour", "price": 100.0, "reference_price": 100.0, "unit_cost": 40.0, "fixed_costs": 1000.0}
    offer.update(offer_overrides)
    return MarketModel(
        market_name="Test", market_size=10_000,
        segments=[Segment(key="a", name="A", share=1.0, price_elasticity=-2.0)],
        channels=[Channel(key="ads", name="Ads", budget=1000, cpm=10, audience_size=50_000,
                          engagement_rate=0.1, lead_rate=0.5, conversion_rate=0.2)],
        offer=Offer(**offer),
    )


def test_funnel_math_matches_hand_calculation():
    k = simulate(tiny_model())["kpis"]
    impressions = 1000 / 10 * 1000
    reach = 50_000 * (1 - math.exp(-impressions / 50_000))
    customers = reach * 0.1 * 0.5 * 0.2
    assert k["impressions"] == pytest.approx(impressions)
    assert k["reach"] == pytest.approx(reach)
    assert k["customers"] == pytest.approx(customers)
    assert k["revenue"] == pytest.approx(customers * 100)
    assert k["profit"] == pytest.approx(customers * 60 - 1000 - 1000)
    assert k["break_even_customers"] == pytest.approx(2000 / 60)


def test_constant_elasticity_price_response():
    base = simulate(tiny_model())["kpis"]["customers"]
    higher = simulate(tiny_model(price=110.0))["kpis"]["customers"]
    assert higher / base == pytest.approx((110 / 100) ** -2.0)


def test_reach_saturates_with_budget():
    small = simulate(apply_levers(tiny_model(), [{"type": "set_budget", "channel": "ads", "value": 1000}]))["kpis"]["reach"]
    big = simulate(apply_levers(tiny_model(), [{"type": "set_budget", "channel": "ads", "value": 10000}]))["kpis"]["reach"]
    assert big < 10 * small and big <= 50_000


def test_levers_reallocate_and_rescale_segments():
    model = default_model(name="Toba", offering="cultural experience", inputs={"target_price": 150000, "price_points": POINTS})
    moved = apply_levers(model, [{"type": "reallocate_budget", "from": "instagram", "to": "tiktok", "share": 0.3}])
    ig = next(c for c in moved.channels if c.key == "instagram")
    tt = next(c for c in moved.channels if c.key == "tiktok")
    assert ig.budget == pytest.approx(15_000_000 * 0.7) and tt.budget == pytest.approx(10_000_000 + 4_500_000)
    shifted = apply_levers(model, [{"type": "set_segment_share", "segment": "gen_z", "value": 0.4}])
    assert sum(s.share for s in shifted.segments) == pytest.approx(1.0)
    assert next(s for s in shifted.segments if s.key == "gen_z").share == 0.4
    with pytest.raises(ValueError):
        apply_levers(model, [{"type": "teleport"}])


def test_competitor_price_cut_reduces_customers():
    model = default_model(name="Toba", offering="cultural experience", inputs={"target_price": 150000, "price_points": POINTS})
    base = simulate(model)["kpis"]["customers"]
    cut = simulate(apply_levers(model, [{"type": "competitor_price_change", "competitor": "village_tour", "pct": -0.25}]))
    assert cut["kpis"]["customers"] < base


def test_wtp_multiplier_recovers_group_share():
    m = wtp_multiplier_for(POINTS, 150000, 0.83)
    assert 150000 / m == pytest.approx(100000, rel=0.01)


def test_graph1_scenarios_and_analyses():
    model = default_model(name="Toba", offering="cultural experience", inputs={"target_price": 150000, "price_points": POINTS})
    assert model.offer.price == 180000  # Graph1: "reduce price from Rp 180,000 to Rp 150,000"
    names = [s["name"] for s in graph1_scenarios(model, 150000)]
    assert len(names) == 4
    steps = analysis.waterfall(model, [{"type": "set_price", "value": 150000}])
    assert steps[0]["value"] + steps[1]["delta"] == pytest.approx(steps[-1]["value"])
    sens = analysis.sensitivity(model)
    assert sens["rows"] and sens["rows"][0]["swing"] >= sens["rows"][-1]["swing"]
    mc1 = analysis.monte_carlo(model, 300, seed=3)
    mc2 = analysis.monte_carlo(model, 300, seed=3)
    assert mc1["profit"] == mc2["profit"] and mc1["profit"]["p10"] <= mc1["profit"]["p50"] <= mc1["profit"]["p90"]
    opt = analysis.optimize_media(model)
    assert opt["optimized_value"] >= opt["baseline_value"] - 1e-6
    assert sum(a["optimized"] for a in opt["allocation"]) == pytest.approx(opt["total_budget"])


def test_segment_shares_must_sum_to_one():
    with pytest.raises(ValueError):
        MarketModel(market_name="x", market_size=1, segments=[Segment(key="a", name="A", share=0.5)],
                    channels=[Channel(key="c", name="C", budget=0, cpm=0, audience_size=1, engagement_rate=0, lead_rate=0,
                                      conversion_rate=0)],
                    offer=Offer(name="o", price=1, reference_price=1, unit_cost=0, fixed_costs=0))


def test_strategy_api_flow(local_client, project):
    pid = project["id"]
    c = local_client
    created = c.post(f"/api/v1/projects/{pid}/scenarios/baseline", json={}).json()
    baseline = created["baseline"]
    assert baseline["results"]["kpis"]["customers"] > 0 and len(created["scenarios"]) >= 3
    first = created["scenarios"][0]
    assert "comparison" in first["results"] and first["results"]["waterfall"][0]["label"] == "Baseline"
    custom = c.post(f"/api/v1/projects/{pid}/scenarios", json={
        "baseline_id": baseline["id"], "name": "Bigger TikTok", "levers": [{"type": "set_budget", "channel": "tiktok", "value": 20000000}]})
    assert custom.status_code == 201
    bad = c.post(f"/api/v1/projects/{pid}/scenarios", json={"baseline_id": baseline["id"], "name": "Bad",
                                                             "levers": [{"type": "set_budget", "channel": "fax", "value": 1}]})
    assert bad.status_code == 422
    assert c.get(f"/api/v1/projects/{pid}/scenarios/{baseline['id']}/sensitivity").json()["rows"]
    assert c.get(f"/api/v1/projects/{pid}/scenarios/{baseline['id']}/monte-carlo?n=300").json()["runs"] > 0
    assert c.get(f"/api/v1/projects/{pid}/scenarios/{baseline['id']}/price-curve").json()["points"]
    ids = f"{baseline['id']},{custom.json()['id']}"
    assert len(c.get(f"/api/v1/projects/{pid}/scenarios/compare?ids={ids}").json()["scenarios"]) == 2

    # Editing the baseline re-simulates its scenarios.
    model = baseline["model"]
    model["offer"]["unit_cost"] = model["offer"]["unit_cost"] * 2
    before = c.get(f"/api/v1/projects/{pid}/scenarios/{first['id']}").json()["results"]["kpis"]["profit"]
    c.patch(f"/api/v1/projects/{pid}/scenarios/{baseline['id']}", json={"model": model})
    after = c.get(f"/api/v1/projects/{pid}/scenarios/{first['id']}").json()["results"]["kpis"]["profit"]
    assert after < before

    decision = c.post(f"/api/v1/projects/{pid}/decisions", json={
        "title": "Launch at the tested price", "decision": "Launch at Rp 150,000 with a pre-sale test.",
        "scenario_id": first["id"]}).json()
    assert decision["status"] == "proposed"
    pending = [a for a in c.get(f"/api/v1/projects/{pid}/approvals").json() if a["action"] == "approve_decision"]
    assert pending
    decided = c.post(f"/api/v1/projects/{pid}/approvals/{pending[0]['id']}/decide", json={"decision": "approved"}).json()
    assert decided["outcome"]["status"] == "approved"
    assert c.get(f"/api/v1/projects/{pid}/scenarios/{first['id']}").json()["status"] == "adopted"
