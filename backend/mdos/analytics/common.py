"""Shared result types and helpers for analytics functions."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from ..jsonutil import to_jsonable

OK, WARNING, VIOLATED, NOT_APPLICABLE = "ok", "warning", "violated", "not_applicable"


class AnalysisError(ValueError):
    """Raised when an analysis cannot run on the given data (clear message for the user)."""


@dataclass
class Check:
    name: str
    status: str
    detail: str
    value: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return to_jsonable({"name": self.name, "status": self.status, "detail": self.detail, "value": self.value})


@dataclass
class EvidenceCandidate:
    """A factual statement derived from an analysis that can be saved as an Evidence record."""

    key: str
    title: str
    statement: str
    n: int | None = None
    effect_size: float | None = None
    effect_label: str = ""
    p_value: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    strength: str = "moderate"
    value: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return to_jsonable(self.__dict__)


@dataclass
class AnalysisResult:
    method: str
    title: str
    n: int | None
    result: dict[str, Any]
    assumptions: list[Check]
    summary: str
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    evidence: list[EvidenceCandidate] = field(default_factory=list)
    charts: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return to_jsonable(
            {
                "method": self.method,
                "title": self.title,
                "n": self.n,
                "summary": self.summary,
                "result": self.result,
                "assumptions": [c.as_dict() for c in self.assumptions],
                "warnings": self.warnings,
                "limitations": self.limitations,
                "evidence": [e.as_dict() for e in self.evidence],
                "charts": self.charts,
            }
        )


# ------------------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------------------


def require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise AnalysisError(f"Column(s) not found in dataset: {', '.join(missing)}")


def numeric(series: pd.Series) -> pd.Series:
    """Coerce to float, turning non-numeric values into NaN."""
    if pd.api.types.is_bool_dtype(series):
        return series.astype(float)
    return pd.to_numeric(series, errors="coerce").astype(float)


def fmt_p(p: float | None) -> str:
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "p = n/a"
    if p < 0.001:
        return "p < .001"
    return f"p = {p:.3f}".replace("0.", ".", 1)


def fmt_num(x: float | None, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "n/a"
    return f"{x:,.{digits}f}"


def fmt_pct(x: float | None, digits: int = 1) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{100 * x:.{digits}f}%"


def wilson_ci(successes: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a proportion (well behaved for small n and extreme p)."""
    if n <= 0:
        return (float("nan"), float("nan"))
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def mean_ci(values: np.ndarray, confidence: float = 0.95) -> tuple[float, float]:
    n = len(values)
    if n < 2:
        return (float("nan"), float("nan"))
    m = float(np.mean(values))
    se = float(np.std(values, ddof=1) / math.sqrt(n))
    t = stats.t.ppf(1 - (1 - confidence) / 2, n - 1)
    return (m - t * se, m + t * se)


def strength_from_test(p: float | None, n: int | None, effect_label: str = "") -> str:
    """Heuristic evidence strength used across methods (documented in docs/17-methods-reference.md)."""
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "insufficient"
    small_n = n is not None and n < 50
    if p < 0.01 and not small_n and effect_label not in ("negligible", ""):
        return "strong" if effect_label in ("medium", "large") or (n or 0) >= 200 else "moderate"
    if p < 0.05:
        return "weak" if small_n else "moderate"
    if p < 0.10:
        return "weak"
    return "insufficient"


def strength_from_proportion(n: int, ci_low: float, ci_high: float) -> str:
    half_width = (ci_high - ci_low) / 2
    if n >= 200 and half_width <= 0.07:
        return "strong"
    if n >= 100 and half_width <= 0.10:
        return "moderate"
    if n >= 30:
        return "weak"
    return "insufficient"


def label_r(r: float) -> str:
    a = abs(r)
    if a < 0.1:
        return "negligible"
    if a < 0.3:
        return "small"
    if a < 0.5:
        return "medium"
    return "large"


def label_f2(f2: float) -> str:
    if f2 < 0.02:
        return "negligible"
    if f2 < 0.15:
        return "small"
    if f2 < 0.35:
        return "medium"
    return "large"


def label_cramers_v(v: float, df_min: int) -> str:
    """Cohen's thresholds for Cramér's V depend on min(r, c) - 1."""
    thresholds = {1: (0.10, 0.30, 0.50), 2: (0.07, 0.21, 0.35), 3: (0.06, 0.17, 0.29)}
    small, medium, large = thresholds.get(df_min, (0.05, 0.15, 0.25))
    if v < small:
        return "negligible"
    if v < medium:
        return "small"
    if v < large:
        return "medium"
    return "large"


def label_odds_ratio(odds_ratio: float) -> str:
    """Chen, Cohen and Chen (2010) approximate thresholds for odds ratios."""
    o = odds_ratio if odds_ratio >= 1 else 1 / odds_ratio if odds_ratio > 0 else float("inf")
    if o < 1.68:
        return "negligible"
    if o < 3.47:
        return "small"
    if o < 6.71:
        return "medium"
    return "large"


def holm_adjust(pvalues: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values (monotone)."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        value = min(1.0, (m - rank) * pvalues[i])
        running = max(running, value)
        adjusted[i] = running
    return adjusted


ASSOCIATION_NOTE = (
    "Results describe associations in the sample. Cross-sectional survey data cannot establish cause and effect."
)
