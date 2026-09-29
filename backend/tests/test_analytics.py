"""Statistical validation of the analytics package against independent oracles."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.proportion import proportions_ztest

from mdos.analytics import (
    cleaning,
    correlation,
    crosstab,
    descriptive,
    power,
    pricing,
    process,
    quality,
    regression,
    reliability,
    segmentation,
    sentiment,
    text,
)
from mdos.analytics.common import AnalysisError, holm_adjust, wilson_ci
from mdos.analytics.profiling import infer_type
from mdos.analytics.registry import METHODS, run

RNG = np.random.default_rng(7)


# ------------------------------------------------------------------ profiling and quality


def test_infer_type_rules():
    df = pd.DataFrame({
        "respondent_id": [f"R{i:03d}" for i in range(50)],
        "ci1": RNG.integers(1, 6, 50),
        "age": RNG.integers(18, 70, 50),
        "wtp150": RNG.choice(["Ya", "Tidak"], 50),
        "origin": RNG.choice(["Domestic", "International", "Local"], 50),
        "vw_cheap": RNG.integers(50, 150, 50) * 1000,
        "comment": ["Pemandangan danau sangat indah dan pemandu ramah sekali"] * 50,
    })
    types = {c: infer_type(df[c], c) for c in df.columns}
    assert types == {"respondent_id": "id", "ci1": "likert", "age": "numeric", "wtp150": "binary",
                     "origin": "categorical", "vw_cheap": "price", "comment": "text"}


def test_quality_flags_planted_issues():
    n = 60
    df = pd.DataFrame({f"q{i}": RNG.integers(1, 6, n) for i in range(1, 8)})
    df.loc[3, [f"q{i}" for i in range(1, 8)]] = 3  # straight-liner
    df.loc[5, "q2"] = 9  # out of range
    df["duration_sec"] = RNG.integers(400, 900, n)
    df.loc[7, "duration_sec"] = 30  # speeder
    df["email"] = [f"user{i}@mail.com" for i in range(n)]
    df = pd.concat([df, df.iloc[[10]]], ignore_index=True)  # duplicate
    report = quality.diagnose(df)
    checks = {i["check"] for i in report["issues"]}
    assert {"straightlining", "out_of_range", "speeders", "personal_data", "duplicate_rows"} <= checks
    straight = next(i for i in report["issues"] if i["check"] == "straightlining")
    assert 3 in straight["rows"]
    assert 0 <= report["quality_score"] < 100
    cleaned, _ = cleaning.apply_operations(df, [{"op": "pseudonymize", "columns": ["email"]}])
    assert "personal_data" not in {i["check"] for i in quality.diagnose(cleaned)["issues"]}


def test_cleaning_plan_and_lineage_log():
    df = pd.DataFrame({"a": [1, 2, 2, 4, 5], "b": [1, 1, 1, 9, 2], "email": list("vwxyz")})
    df.loc[2] = df.loc[1]
    plan = [{"op": "pseudonymize", "columns": ["email"]}, {"op": "drop_duplicates"},
            {"op": "set_out_of_range_missing", "column": "b", "min": 1, "max": 5},
            {"op": "drop_rows", "rows": [0], "reason": "test"},
            {"op": "compute_scale", "name": "ab", "items": ["a", "b"], "min_items": 1}]
    out, log = cleaning.apply_operations(df, plan)
    assert len(out) == 3 and [entry["op"] for entry in log] == [p["op"] for p in plan]
    assert out["email"].str.len().eq(12).all()
    assert out["b"].isna().sum() == 1
    assert "ab" in out.columns
    with pytest.raises(AnalysisError):
        cleaning.apply_operations(df, [{"op": "delete_everything"}])


# ------------------------------------------------------------------ descriptive, crosstab, correlation


def test_descriptive_matches_numpy():
    x = RNG.normal(3.5, 0.8, 200)
    df = pd.DataFrame({"x": x, "g": RNG.choice(["a", "b"], 200)})
    res = descriptive.describe(df, ["x", "g"], {"x": "numeric", "g": "categorical"})
    row = res.result["numeric"][0]
    assert row["mean"] == pytest.approx(x.mean())
    assert row["sd"] == pytest.approx(x.std(ddof=1))
    t = stats.t.ppf(0.975, 199)
    assert row["ci_low"] == pytest.approx(x.mean() - t * x.std(ddof=1) / math.sqrt(200))
    assert sum(f["count"] for f in res.result["categorical"][0]["frequencies"]) == 200
    assert res.assumptions and all(c.status for c in res.assumptions)


def test_crosstab_matches_scipy():
    df = pd.DataFrame({"origin": ["dom"] * 60 + ["intl"] * 40,
                       "buy": ["yes"] * 25 + ["no"] * 35 + ["yes"] * 30 + ["no"] * 10})
    res = crosstab.crosstab(df, "origin", "buy")
    chi2, p, dof, _ = stats.chi2_contingency(pd.crosstab(df.origin, df.buy).to_numpy(), correction=False)
    assert res.result["chi2"] == pytest.approx(chi2)
    assert res.result["p_value"] == pytest.approx(p)
    assert res.result["cramers_v"] == pytest.approx(math.sqrt(chi2 / 100))


def test_correlation_and_holm():
    x = RNG.normal(size=150)
    y = 0.6 * x + RNG.normal(scale=0.8, size=150)
    z = RNG.normal(size=150)
    res = correlation.correlation(pd.DataFrame({"x": x, "y": y, "z": z}), ["x", "y", "z"])
    pair = next(p for p in res.result["pairs"] if {p["x"], p["y"]} == {"x", "y"})
    r, p = stats.pearsonr(x, y)
    assert pair["r"] == pytest.approx(r) and pair["p"] == pytest.approx(p)
    assert holm_adjust([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])


# ------------------------------------------------------------------ regression


def _regression_data(n=300):
    x1 = RNG.normal(size=n)
    x2 = RNG.normal(size=n)
    grp = RNG.choice(["A", "B", "C"], n)
    y = 1.0 + 0.5 * x1 - 0.3 * x2 + np.where(grp == "B", 0.4, 0) + RNG.normal(scale=1.0, size=n)
    return pd.DataFrame({"y": y, "x1": x1, "x2": x2, "grp": grp})


def test_ols_matches_statsmodels_formula():
    df = _regression_data()
    res = regression.ols(df, "y", ["x1", "x2", "grp"], robust="none")
    reference = df.grp.value_counts().index[0]
    ref = smf.ols(f"y ~ x1 + x2 + C(grp, Treatment(reference='{reference}'))", df).fit()
    coefs = {c["term"]: c for c in res.result["coefficients"]}
    assert coefs["x1"]["b"] == pytest.approx(ref.params["x1"])
    assert coefs["x2"]["se"] == pytest.approx(ref.bse["x2"])
    assert res.result["r2"] == pytest.approx(ref.rsquared)
    assert len(res.assumptions) >= 6
    assert any(e.key == "ols:y:x1" for e in res.evidence)
    assert "associated" in next(e.statement for e in res.evidence if e.key == "ols:y:x1")


def test_ols_recovers_exact_coefficients_without_noise():
    x = np.arange(50, dtype=float)
    z = np.sin(x)
    df = pd.DataFrame({"y": 2 + 3 * x - 1.5 * z, "x": x, "z": z})
    res = regression.ols(df, "y", ["x", "z"], robust="none")
    coefs = {c["term"]: c["b"] for c in res.result["coefficients"]}
    assert coefs["x"] == pytest.approx(3.0) and coefs["z"] == pytest.approx(-1.5) and coefs["Intercept"] == pytest.approx(2.0)


def test_ols_switches_to_robust_errors_under_heteroscedasticity():
    n = 400
    x = RNG.uniform(0, 10, n)
    y = 2 * x + RNG.normal(scale=0.2 + x, size=n)
    res = regression.ols(pd.DataFrame({"y": y, "x": x}), "y", ["x"], robust="auto")
    assert res.result["robust_se"] is True
    ref = sm.OLS(y, sm.add_constant(x)).fit(cov_type="HC3")
    assert next(c for c in res.result["coefficients"] if c["term"] == "x")["se"] == pytest.approx(ref.bse[1])


def test_logistic_matches_statsmodels_and_odds_ratios():
    n = 500
    x = RNG.normal(size=n)
    p = 1 / (1 + np.exp(-(-0.3 + 1.1 * x)))
    y = np.where(RNG.uniform(size=n) < p, "Ya", "Tidak")
    df = pd.DataFrame({"buy": y, "x": x})
    res = regression.logistic(df, "buy", ["x"])
    ref = sm.Logit((df.buy == "Ya").astype(float), sm.add_constant(df.x)).fit(disp=0)
    row = next(c for c in res.result["coefficients"] if c["term"] == "x")
    assert row["b"] == pytest.approx(ref.params["x"], rel=1e-5)
    assert row["odds_ratio"] == pytest.approx(math.exp(ref.params["x"]), rel=1e-5)
    assert 0.5 < res.result["auc"] <= 1.0


# ------------------------------------------------------------------ reliability and PROCESS


def test_cronbach_alpha_formula():
    items = np.array([[3, 4, 3], [2, 2, 3], [5, 5, 4], [4, 4, 4], [1, 2, 2], [3, 3, 3], [4, 5, 5], [2, 3, 2],
                      [5, 4, 5], [3, 3, 4]], dtype=float)
    k = 3
    expected = k / (k - 1) * (1 - items.var(axis=0, ddof=1).sum() / items.sum(axis=1).var(ddof=1))
    assert reliability.cronbach_alpha_matrix(items) == pytest.approx(expected)
    same = np.column_stack([items[:, 0]] * 3)
    assert reliability.cronbach_alpha_matrix(same) == pytest.approx(1.0)


def test_reliability_flags_reverse_coded_item():
    base = RNG.integers(1, 6, 120).astype(float)
    df = pd.DataFrame({"a1": base, "a2": np.clip(base + RNG.integers(-1, 2, 120), 1, 5),
                       "a3": np.clip(base + RNG.integers(-1, 2, 120), 1, 5), "a4": 6 - base})
    res = reliability.reliability(df, ["a1", "a2", "a3", "a4"], "Test")
    reverse = next(c for c in res.assumptions if c.name == "Reverse-coded items")
    assert reverse.status == "violated" and "a4" in reverse.detail


def test_mediation_paths_match_ols_and_identity_holds():
    n = 400
    x = RNG.normal(size=n)
    m = 0.5 * x + RNG.normal(size=n)
    y = 0.4 * m + 0.2 * x + RNG.normal(size=n)
    df = pd.DataFrame({"x": x, "m": m, "y": y})
    res = process.mediation(df, "x", "m", "y", n_boot=2000, seed=1)
    paths = {p["path"]: p["b"] for p in res.result["paths"]}
    a_ref = sm.OLS(m, sm.add_constant(x)).fit().params[1]
    assert paths["a"] == pytest.approx(a_ref)
    assert paths["c"] == pytest.approx(paths["c'"] + paths["a"] * paths["b"])  # exact for OLS
    low, high = res.result["boot_ci"]
    assert low < 0.5 * 0.4 < high and low > 0
    again = process.mediation(df, "x", "m", "y", n_boot=2000, seed=1)
    assert again.result["boot_ci"] == res.result["boot_ci"]  # reproducible with the recorded seed


def test_moderation_interaction_and_simple_slopes():
    n = 500
    x = RNG.normal(size=n)
    w = RNG.normal(size=n)
    y = 0.3 * x + 0.2 * w + 0.4 * x * w + RNG.normal(size=n)
    df = pd.DataFrame({"x": x, "w": w, "y": y})
    res = process.moderation(df, "x", "w", "y")
    xc, wc = x - x.mean(), w - w.mean()
    ref = sm.OLS(y, sm.add_constant(np.column_stack([xc, wc, xc * wc]))).fit()
    inter = next(c for c in res.result["coefficients"] if " x " in c["term"])
    assert inter["b"] == pytest.approx(ref.params[3])
    slopes = res.result["simple_slopes"]
    assert slopes[0]["slope"] < slopes[1]["slope"] < slopes[2]["slope"]
    sd = w.std(ddof=1)
    cov = ref.cov_params()
    se_high = math.sqrt(cov[1, 1] + sd**2 * cov[3, 3] + 2 * sd * cov[1, 3])
    assert slopes[2]["se"] == pytest.approx(se_high)


# ------------------------------------------------------------------ pricing


def test_van_westendorp_known_intersections():
    # Uniform, symmetric answers produce curves that cross at predictable points.
    rows = []
    for base in range(100, 201, 5):
        rows.append({"tc": base * 400, "c": base * 700, "e": base * 1300, "te": base * 1600})
    df = pd.DataFrame(rows * 3)
    res = pricing.van_westendorp(df, "tc", "c", "e", "te", target_price=150_000)
    r = res.result
    assert r["pmc"] < r["opp"] < r["pme"]
    assert r["pmc"] <= r["ipp"] <= r["pme"]
    assert r["n_invalid"] == 0
    assert 0.0 <= r["target"]["acceptable"] <= 1.0


def test_van_westendorp_excludes_inconsistent_answers():
    good = pd.DataFrame({"tc": [50_000] * 30, "c": [100_000] * 30, "e": [180_000] * 30, "te": [250_000] * 30})
    bad = pd.DataFrame({"tc": [200_000] * 5, "c": [100_000] * 5, "e": [180_000] * 5, "te": [250_000] * 5})
    res = pricing.van_westendorp(pd.concat([good, bad]), "tc", "c", "e", "te")
    assert res.result["n_invalid"] == 5 and res.n == 30


def test_gabor_granger_shares_and_revenue_max():
    n = 200
    df = pd.DataFrame({
        "gg100": ["Ya"] * 160 + ["Tidak"] * 40,
        "gg150": ["Ya"] * 120 + ["Tidak"] * 80,
        "gg200": ["Ya"] * 70 + ["Tidak"] * 130,
    })
    res = pricing.gabor_granger(df, {"100000": "gg100", "150000": "gg150", "200000": "gg200"}, target_price=150000)
    shares = {p["price"]: p["share"] for p in res.result["points"]}
    assert shares == {100000.0: 0.8, 150000.0: 0.6, 200000.0: 0.35}
    assert res.result["revenue_max_price"] == 150000.0  # 90k > 80k > 70k
    lo, hi = wilson_ci(120, n)
    point = next(p for p in res.result["points"] if p["price"] == 150000.0)
    assert (point["ci_low"], point["ci_high"]) == pytest.approx((lo, hi))


def test_wtp_by_group():
    df = pd.DataFrame({"wtp": ["Ya"] * 70 + ["Tidak"] * 30, "origin": ["dom"] * 50 + ["intl"] * 50})
    res = pricing.wtp_at_price(df, "wtp", 150000, group="origin")
    assert res.result["share"] == pytest.approx(0.7)
    assert {g["group"] for g in res.result["groups"]} == {"dom", "intl"}


# ------------------------------------------------------------------ segmentation, text, sentiment


def test_segmentation_requires_objective_and_recovers_clusters():
    centers = [(1, 1), (5, 5), (1, 5)]
    rows = []
    for cx, cy in centers:
        rows.append(pd.DataFrame({"a": RNG.normal(cx, 0.3, 60), "b": RNG.normal(cy, 0.3, 60)}))
    df = pd.concat(rows, ignore_index=True)
    with pytest.raises(AnalysisError):
        segmentation.segment(df, ["a", "b"], objective="", rationale="")
    res = segmentation.segment(df, ["a", "b"], objective="Find groups with different needs for targeting",
                               rationale="Needs a and b drive purchase decisions in prior research")
    assert res.result["k"] == 3
    assert res.result["stability_ari"] > 0.95
    assert all(abs(s["share"] - 1 / 3) < 0.05 for s in res.result["segments"])


def test_sentiment_handles_negation_intensifiers_and_bilingual_text():
    cases = {
        "The lake view is absolutely beautiful and the guide was friendly": "positive",
        "Pemandangannya indah banget, pemandunya ramah": "positive",
        "Tidak bagus, toiletnya kotor dan bau": "negative",
        "Not worth the price, very disappointing": "negative",
        "Harganya kemahalan dan antri lama sekali": "negative",
        "Kami tiba jam sepuluh pagi": "neutral",
        "The boat was late but the cultural show was amazing": "positive",
        "Tempatnya bagus tapi jalannya rusak parah dan macet": "negative",
        "Very little information on the official website.": "negative",
        "No clear schedule online.": "negative",
    }
    for text_value, expected in cases.items():
        assert sentiment.score_text(text_value)["label"] == expected, text_value
    negated = sentiment.score_text("not good")["compound"]
    assert negated < 0 < sentiment.score_text("good")["compound"]


def test_text_themes_and_language_detection():
    docs = (["booking online susah dan ribet, website error"] * 12 + ["the cultural dance show and ulos weaving were amazing"] * 12
            + ["jalan menuju danau macet dan rusak"] * 12)
    res = text.text_themes(pd.DataFrame({"t": docs}), "t", n_topics=3)
    assert len(res.result["themes"]) == 3
    assert text.detect_language("the view of the lake is beautiful") == "en"
    assert text.detect_language("pemandangan yang sangat indah dan tenang di sini") == "id"


# ------------------------------------------------------------------ power and registry


def test_sample_size_formulas():
    assert power.sample_size_proportion(0.5, 0.05, 0.95)["n"] == 385
    assert power.sample_size_proportion(0.5, 0.05, 0.95, population=1000)["n"] == 278
    ab = power.ab_sample_size(0.10, 0.20)
    assert 3500 < ab["n_per_arm"] < 4000


def test_two_proportion_test_matches_statsmodels():
    res = power.two_proportion_test(120, 1000, 150, 1000)
    z, p = proportions_ztest([150, 120], [1000, 1000])
    assert res["z"] == pytest.approx(z) and res["p_value"] == pytest.approx(p)


def test_every_method_reports_assumptions_via_registry():
    df = _regression_data()
    df["t"] = ["good view"] * 150 + ["bad road and traffic"] * 150
    parsed, res = run("regression_ols", df, {"dv": "y", "predictors": ["x1"]})
    assert res.assumptions
    parsed, res = run("sentiment", df, {"text_column": "t"})
    assert res.assumptions
    assert set(METHODS) >= {"descriptive", "crosstab", "correlation", "regression_ols", "regression_logistic", "reliability",
                            "mediation", "moderation", "van_westendorp", "gabor_granger", "wtp", "segmentation",
                            "text_themes", "sentiment"}
    with pytest.raises(AnalysisError):
        run("regression_ols", df, {"dv": "y"})
