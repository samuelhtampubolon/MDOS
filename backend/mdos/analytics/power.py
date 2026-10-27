"""Sample size, margin of error, A/B test sizing and the two-proportion test."""

from __future__ import annotations

import math

from scipy import stats

from .common import AnalysisError, wilson_ci


def _z(confidence: float) -> float:
    return float(stats.norm.ppf(1 - (1 - confidence) / 2))


def fpc_adjust(n: float, population: int | None) -> int:
    if population and population > 0:
        n = n / (1 + (n - 1) / population)
    return int(math.ceil(n))


def sample_size_proportion(p: float = 0.5, margin: float = 0.05, confidence: float = 0.95,
                           population: int | None = None) -> dict:
    if not (0 < p < 1) or not (0 < margin < 1):
        raise AnalysisError("p and margin must be between 0 and 1.")
    z = _z(confidence)
    n0 = z**2 * p * (1 - p) / margin**2
    return {"n": fpc_adjust(n0, population), "n_infinite": int(math.ceil(n0)), "z": z, "p": p, "margin": margin,
            "confidence": confidence, "population": population,
            "formula": "n = z^2 p(1-p) / e^2, with finite population correction n / (1 + (n-1)/N)"}


def sample_size_mean(sd: float, margin: float, confidence: float = 0.95, population: int | None = None) -> dict:
    if sd <= 0 or margin <= 0:
        raise AnalysisError("sd and margin must be positive.")
    z = _z(confidence)
    n0 = (z * sd / margin) ** 2
    return {"n": fpc_adjust(n0, population), "n_infinite": int(math.ceil(n0)), "z": z, "sd": sd, "margin": margin,
            "confidence": confidence, "population": population, "formula": "n = (z sd / e)^2"}


def margin_of_error(n: int, p: float = 0.5, confidence: float = 0.95, population: int | None = None) -> float:
    if n <= 0:
        raise AnalysisError("n must be positive.")
    z = _z(confidence)
    moe = z * math.sqrt(p * (1 - p) / n)
    if population and population > n:
        moe *= math.sqrt((population - n) / (population - 1))
    return moe


def ab_sample_size(baseline: float, mde_relative: float, alpha: float = 0.05, power: float = 0.8,
                   two_sided: bool = True) -> dict:
    """Per-arm sample size to detect a relative lift in a conversion rate (normal approximation)."""
    if not (0 < baseline < 1):
        raise AnalysisError("Baseline rate must be between 0 and 1.")
    p1 = baseline
    p2 = baseline * (1 + mde_relative)
    if not (0 < p2 < 1) or p1 == p2:
        raise AnalysisError("The minimum detectable effect implies an impossible target rate.")
    z_a = float(stats.norm.ppf(1 - alpha / 2)) if two_sided else float(stats.norm.ppf(1 - alpha))
    z_b = float(stats.norm.ppf(power))
    p_bar = (p1 + p2) / 2
    num = (z_a * math.sqrt(2 * p_bar * (1 - p_bar)) + z_b * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    n = int(math.ceil(num / (p2 - p1) ** 2))
    return {"n_per_arm": n, "total": 2 * n, "baseline": p1, "target": p2, "mde_relative": mde_relative,
            "alpha": alpha, "power": power, "two_sided": two_sided}


def two_proportion_test(x1: int, n1: int, x2: int, n2: int, confidence: float = 0.95) -> dict:
    """Pooled z-test for a difference in proportions (arm 2 versus arm 1) with an unpooled Wald interval."""
    if min(n1, n2) <= 0 or not (0 <= x1 <= n1) or not (0 <= x2 <= n2):
        raise AnalysisError("Counts must satisfy 0 <= conversions <= visitors, with visitors above zero.")
    p1, p2 = x1 / n1, x2 / n2
    pooled = (x1 + x2) / (n1 + n2)
    se_pooled = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    z = (p2 - p1) / se_pooled if se_pooled > 0 else 0.0
    p_value = float(2 * (1 - stats.norm.cdf(abs(z))))
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    zc = _z(confidence)
    diff = p2 - p1
    return {
        "p1": p1, "p2": p2, "difference": diff, "ci_low": diff - zc * se, "ci_high": diff + zc * se,
        "relative_lift": (diff / p1) if p1 > 0 else None, "z": z, "p_value": p_value,
        "arm1_ci": wilson_ci(x1, n1, confidence), "arm2_ci": wilson_ci(x2, n2, confidence),
        "significant": p_value < (1 - confidence),
    }


def min_sample_rules(n_predictors: int) -> dict:
    return {
        "regression_green_1991": 50 + 8 * n_predictors,
        "regression_per_predictor_15": 15 * n_predictors,
        "note": "Rules of thumb; a formal power analysis depends on the expected effect size.",
    }
