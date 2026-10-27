"""Journey engine math, VOC mapping and the experiment loop back to research evidence."""

from __future__ import annotations

import pytest
from conftest import SAMPLES

from mdos.journey import engine
from mdos.journey.templates import stages_for, template
from mdos.journey.voc import classify_stage, split_sentences


def test_stage_classification_bilingual():
    stages = template("tourism")["stages"]
    assert classify_stage("Booking ribet, harus transfer manual lalu konfirmasi lewat WhatsApp.", stages) == "book"
    assert classify_stage("The road from Medan was congested and damaged.", stages) == "arrive"
    assert classify_stage("Spot fotonya keren banget, cocok buat Instagram.", stages) == "share"
    assert classify_stage("Found this place through an Instagram reel.", stages) == "discover"
    assert split_sentences("One. Two! Three?") == ["One.", "Two!", "Three?"]


def test_reduce_steps_math_and_levels():
    stages = stages_for("tourism")
    iv = {"stage_key": "book", "kind": "reduce_steps", "params": {"steps_from": 5, "steps_to": 2}}
    mid = next(s for s in engine.apply_intervention(stages, iv, "mid") if s["key"] == "book")["conversion"]
    high = next(s for s in engine.apply_intervention(stages, iv, "high") if s["key"] == "book")["conversion"]
    theoretical = (0.4 ** (1 / 5)) ** 2
    assert high == pytest.approx(theoretical)
    assert mid == pytest.approx(0.4 + 0.5 * (theoretical - 0.4))
    sim = engine.simulate_intervention(stages, iv, 20000, 150000)
    d = {k: v["delta_customers"] for k, v in sim["levels"].items()}
    assert 0 < d["low"] < d["mid"] < d["high"]


def test_satisfaction_uplift_raises_word_of_mouth_only():
    stages = stages_for("tourism")
    iv = {"stage_key": "experience", "kind": "satisfaction_uplift", "uplift_low": 0.1, "uplift_mid": 0.2, "uplift_high": 0.3}
    before = engine.simulate(stages, 20000, 150000)
    after = engine.simulate(engine.apply_intervention(stages, iv, "mid"), 20000, 150000)
    assert after["customers"] == pytest.approx(before["customers"])  # acquisition funnel unchanged
    assert after["wom_customers"] > before["wom_customers"]


def test_simulation_funnel_math():
    stages = stages_for("tourism")
    sim = engine.simulate(stages, 10000, 100)
    expected = 10000 * 0.30 * 0.60 * 0.35 * 0.40 * 0.95 * 0.98
    assert sim["customers"] == pytest.approx(expected)
    assert sim["revenue"] == pytest.approx(sim["total_customers"] * 100)


def test_prioritize_orders_by_score():
    out = engine.prioritize([{"stage": "book", "frequency": 0.1, "severity": 0.5}, {"stage": "arrive", "frequency": 0.2, "severity": 0.6}])
    assert out[0]["stage"] == "arrive" and out[0]["score"] == pytest.approx(12.0)


def test_journey_api_and_experiment_loop(local_client, project):
    pid = project["id"]
    c = local_client
    with open(SAMPLES / "lake_toba_reviews.csv", "rb") as f:
        ds = c.post(f"/api/v1/projects/{pid}/datasets", files={"file": ("reviews.csv", f, "text/csv")},
                    data={"name": "Reviews", "kind": "reviews"}).json()
    version_id = ds["versions"][0]["id"]
    j = c.post(f"/api/v1/projects/{pid}/journeys", json={"name": "Lake Toba visit", "template": "tourism"}).json()
    assert [s["name"] for s in j["stages"]][:4] == ["Discover", "Search", "Compare", "Book"]
    assert j["touchpoints"]
    j = c.post(f"/api/v1/projects/{pid}/journeys/{j['id']}/voc",
               json={"dataset_version_id": version_id, "text_column": "review_text", "rating_column": "rating"}).json()
    assert j["pain_points"] and all(p["evidence_ids"] for p in j["pain_points"])
    assert j["voc"]["heatmap"]["themes"]
    arrive = next(s for s in j["stages"] if s["key"] == "arrive")
    share = next(s for s in j["stages"] if s["key"] == "share")
    assert arrive["emotion"] < 0 < share["emotion"]

    proposed = c.post(f"/api/v1/projects/{pid}/journeys/{j['id']}/interventions/propose").json()
    assert proposed and all(iv["simulation"]["levels"]["mid"]["delta_customers"] >= 0 for iv in proposed)
    story = next((iv for iv in proposed if "storytelling" in iv["title"].lower()), proposed[0])

    # Booking friction from five steps to two (Graph1 example), added manually.
    manual = c.post(f"/api/v1/projects/{pid}/journeys/{j['id']}/interventions", json={
        "stage_key": "book", "title": "Cut booking from five steps to two", "kind": "reduce_steps",
        "params": {"steps_from": 5, "steps_to": 2}, "uplift_low": 0, "uplift_mid": 0, "uplift_high": 0}).json()
    assert manual["simulation"]["levels"]["mid"]["delta_customers"] > 0

    exp = c.post(f"/api/v1/projects/{pid}/journeys/{j['id']}/interventions/{manual['id']}/experiment").json()
    assert exp["status"] == "draft" and exp["sample_size_per_arm"] > 0
    # Results cannot be recorded before launch approval.
    early = c.post(f"/api/v1/projects/{pid}/experiments/{exp['id']}/results", json={
        "control_visitors": 2000, "control_conversions": 800, "treatment_visitors": 2000, "treatment_conversions": 960})
    assert early.status_code == 422
    approval = next(a for a in c.get(f"/api/v1/projects/{pid}/approvals").json() if a["entity_id"] == exp["id"])
    c.post(f"/api/v1/projects/{pid}/approvals/{approval['id']}/decide", json={"decision": "approved"})
    res = c.post(f"/api/v1/projects/{pid}/experiments/{exp['id']}/results", json={
        "control_visitors": 2000, "control_conversions": 800, "treatment_visitors": 2000, "treatment_conversions": 960}).json()
    ev = res["evidence"]
    assert ev["design"] == "experiment" and ev["origin"] == "experiment" and ev["p_value"] < 0.001
    assert res["experiment"]["status"] == "completed"

    # Causal wording is allowed when the insight rests on experimental evidence (the loop back to research).
    insight = c.post(f"/api/v1/projects/{pid}/insights", json={
        "title": "Two-step booking increases completion",
        "statement": "Reducing booking to two steps increases booking completion.", "evidence_ids": [ev["id"]]})
    assert insight.status_code == 201, insight.text

    # Editing stage assumptions re-simulates interventions.
    stages = j["stages"]
    for s in stages:
        if s["key"] == "book":
            s["conversion"] = 0.5
    updated = c.patch(f"/api/v1/projects/{pid}/journeys/{j['id']}", json={"stages": stages}).json()
    assert updated["simulation"]["customers"] > j["simulation"]["customers"]
    assert story["title"]
