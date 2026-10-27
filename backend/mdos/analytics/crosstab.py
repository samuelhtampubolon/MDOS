"""Cross-tabulation with chi-square test of independence and Cramér's V."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from .common import (
    OK,
    VIOLATED,
    WARNING,
    AnalysisError,
    AnalysisResult,
    Check,
    EvidenceCandidate,
    fmt_num,
    fmt_p,
    label_cramers_v,
    require_columns,
    strength_from_test,
)


def crosstab(df: pd.DataFrame, row: str, col: str, labels: dict[str, str] | None = None) -> AnalysisResult:
    require_columns(df, [row, col])
    labels = labels or {}
    data = df[[row, col]].dropna().astype(str)
    n = len(data)
    if n < 10:
        raise AnalysisError("Cross-tabulation needs at least 10 complete cases.")
    table = pd.crosstab(data[row], data[col])
    if table.shape[0] < 2 or table.shape[1] < 2:
        raise AnalysisError("Both variables need at least two categories with data.")

    observed = table.to_numpy()
    chi2, p, dof, expected = stats.chi2_contingency(observed, correction=False)
    df_min = min(table.shape) - 1
    cramers_v = math.sqrt(chi2 / (n * df_min)) if df_min > 0 else float("nan")
    effect = label_cramers_v(cramers_v, df_min)

    # Adjusted standardized residuals show which cells drive the association.
    row_tot = observed.sum(axis=1, keepdims=True)
    col_tot = observed.sum(axis=0, keepdims=True)
    adj = (observed - expected) / np.sqrt(expected * (1 - row_tot / n) * (1 - col_tot / n))

    low_expected_share = float((expected < 5).mean())
    min_expected = float(expected.min())
    fisher_p = None
    if table.shape == (2, 2):
        fisher_p = float(stats.fisher_exact(observed)[1])

    cells = []
    for i, r in enumerate(table.index):
        for j, c in enumerate(table.columns):
            cells.append({
                "row": r, "col": c, "count": int(observed[i, j]),
                "row_share": observed[i, j] / row_tot[i, 0], "col_share": observed[i, j] / col_tot[0, j],
                "expected": float(expected[i, j]), "adj_residual": float(adj[i, j]),
            })

    expected_ok = low_expected_share <= 0.2 and min_expected >= 1
    checks = [
        Check("Independent observations", OK, "Each respondent appears once (assumed; duplicates are flagged in data quality)."),
        Check("Expected cell counts", OK if expected_ok else (WARNING if min_expected >= 1 else VIOLATED),
              f"{low_expected_share:.0%} of cells have expected counts below 5 (minimum {min_expected:.2f})."
              + ("" if expected_ok else " The chi-square p-value may be inaccurate"
                 + ("; Fisher's exact test is reported." if fisher_p is not None else "; merge sparse categories.")),
              value=low_expected_share),
    ]
    reported_p = fisher_p if (fisher_p is not None and not expected_ok) else float(p)
    row_label, col_label = labels.get(row, row), labels.get(col, col)
    drivers = sorted((c for c in cells if abs(c["adj_residual"]) > 1.96), key=lambda c: -abs(c["adj_residual"]))[:3]
    driver_text = "; ".join(
        f"'{c['row']}' x '{c['col']}' {'over' if c['adj_residual'] > 0 else 'under'}-represented" for c in drivers
    )
    statement = (
        f"{row_label} and {col_label} are {'associated' if reported_p < 0.05 else 'not significantly associated'} "
        f"(chi-square({dof}) = {fmt_num(chi2)}, {fmt_p(reported_p)}, Cramér's V = {fmt_num(cramers_v)}, {effect}, n = {n})."
    )
    evidence = [EvidenceCandidate(
        key=f"crosstab:{row}:{col}", title=f"{row_label} by {col_label}", statement=statement, n=n,
        effect_size=cramers_v, effect_label=effect, p_value=reported_p,
        strength=strength_from_test(reported_p, n, effect),
        value={"chi2": chi2, "dof": dof, "cramers_v": cramers_v, "drivers": driver_text},
    )]
    chart = {"type": "stacked_bar", "title": f"{row_label} by {col_label}", "rows": [str(r) for r in table.index],
             "cols": [str(c) for c in table.columns],
             "data": [[observed[i, j] / row_tot[i, 0] for j in range(table.shape[1])] for i in range(table.shape[0])],
             "format": "percent"}
    return AnalysisResult(
        method="crosstab",
        title=f"Cross-tab: {row_label} by {col_label}",
        n=n,
        result={
            "rows": [str(r) for r in table.index],
            "cols": [str(c) for c in table.columns],
            "cells": cells,
            "chi2": chi2, "dof": dof, "p_value": float(p), "fisher_p": fisher_p, "reported_p": reported_p,
            "cramers_v": cramers_v, "effect_label": effect, "drivers": driver_text,
        },
        assumptions=checks,
        summary=statement,
        limitations=["An association between two categorical variables does not show that one causes the other."],
        evidence=evidence,
        charts=[chart],
    )
