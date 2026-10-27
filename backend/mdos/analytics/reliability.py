"""Internal consistency reliability (Cronbach's alpha) with item diagnostics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .common import (
    NOT_APPLICABLE,
    OK,
    VIOLATED,
    WARNING,
    AnalysisError,
    AnalysisResult,
    Check,
    EvidenceCandidate,
    fmt_num,
    numeric,
    require_columns,
)


def cronbach_alpha_matrix(items: np.ndarray) -> float:
    """alpha = k/(k-1) * (1 - sum(item variances) / variance(total)). Rows = respondents."""
    k = items.shape[1]
    if k < 2:
        raise AnalysisError("Reliability needs at least two items.")
    item_var = items.var(axis=0, ddof=1).sum()
    total_var = items.sum(axis=1).var(ddof=1)
    if total_var == 0:
        return float("nan")
    return float(k / (k - 1) * (1 - item_var / total_var))


def alpha_label(alpha: float) -> str:
    if np.isnan(alpha):
        return "undefined"
    if alpha >= 0.9:
        return "excellent"
    if alpha >= 0.8:
        return "good"
    if alpha >= 0.7:
        return "acceptable"
    if alpha >= 0.6:
        return "questionable"
    return "poor"


def reliability(df: pd.DataFrame, items: list[str], construct: str = "", labels: dict[str, str] | None = None) -> AnalysisResult:
    require_columns(df, items)
    labels = labels or {}
    data = pd.DataFrame({c: numeric(df[c]) for c in items}).dropna()
    n, k = data.shape
    if n < 10:
        raise AnalysisError("Reliability needs at least 10 complete responses.")
    matrix = data.to_numpy()
    alpha = cronbach_alpha_matrix(matrix)
    corr = np.corrcoef(matrix, rowvar=False)
    mean_r = float(corr[np.triu_indices(k, 1)].mean())
    std_alpha = float(k * mean_r / (1 + (k - 1) * mean_r))
    total = matrix.sum(axis=1)
    item_rows = []
    for i, col in enumerate(items):
        rest = total - matrix[:, i]
        r_it = float(np.corrcoef(matrix[:, i], rest)[0, 1]) if np.std(rest) > 0 else float("nan")
        remaining = np.delete(matrix, i, axis=1)
        a_del = cronbach_alpha_matrix(remaining) if k > 2 else float("nan")
        item_rows.append({"item": col, "label": labels.get(col, col), "mean": float(matrix[:, i].mean()),
                          "sd": float(matrix[:, i].std(ddof=1)), "item_total_r": r_it, "alpha_if_deleted": a_del})
    negative = [r["item"] for r in item_rows if r["item_total_r"] < 0]
    weak = [r["item"] for r in item_rows if 0 <= r["item_total_r"] < 0.3]
    improves = [r["item"] for r in item_rows if not np.isnan(r["alpha_if_deleted"]) and r["alpha_if_deleted"] > alpha + 0.02]
    name = construct or "the scale"
    label = alpha_label(alpha)
    checks = [
        Check("Reverse-coded items", VIOLATED if negative else OK,
              f"Negative item-total correlation for {', '.join(negative)}: reverse-code before computing scores."
              if negative else "No negatively correlated items."),
        Check("Item-total correlations", WARNING if weak else OK,
              f"Weak items (corrected r below .30): {', '.join(weak)}." if weak else "All corrected item-total correlations are .30 or higher."),
        Check("Unidimensionality", NOT_APPLICABLE,
              "Alpha assumes the items measure one construct. Confirm with factor analysis (planned for Phase 2)."),
        Check("Tau-equivalence", WARNING, "Alpha is a lower bound when item loadings differ; omega is planned for Phase 2."),
    ]
    statement = (f"Internal consistency of {name} is {label} (Cronbach's alpha = {fmt_num(alpha)}, "
                 f"{k} items, n = {n}).")
    return AnalysisResult(
        method="reliability",
        title=f"Reliability: {name}",
        n=n,
        result={"construct": construct, "items": item_rows, "alpha": alpha, "standardized_alpha": std_alpha,
                "mean_inter_item_r": mean_r, "k": k, "label": label, "items_that_improve_alpha": improves},
        assumptions=checks,
        summary=statement,
        warnings=[f"Removing {', '.join(improves)} would raise alpha by more than .02."] if improves else [],
        limitations=["Alpha increases with the number of items; a high alpha does not prove validity."],
        evidence=[EvidenceCandidate(key=f"alpha:{construct or '+'.join(items)}", title=f"Reliability of {name}",
                                    statement=statement, n=n, effect_size=alpha, effect_label=label,
                                    strength="strong" if alpha >= 0.8 else "moderate" if alpha >= 0.7 else "weak",
                                    value={"alpha": alpha, "k": k})],
        charts=[{"type": "bar", "title": "Corrected item-total correlations", "format": "number",
                 "data": [{"label": r["label"], "value": r["item_total_r"]} for r in item_rows]}],
    )
