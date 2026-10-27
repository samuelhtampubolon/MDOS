"""Pairwise correlation matrix with p-values, Holm correction and assumption checks."""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
from scipy import stats

from .common import (
    ASSOCIATION_NOTE,
    OK,
    WARNING,
    AnalysisError,
    AnalysisResult,
    Check,
    EvidenceCandidate,
    fmt_num,
    fmt_p,
    holm_adjust,
    label_r,
    numeric,
    require_columns,
    strength_from_test,
)


def correlation(df: pd.DataFrame, columns: list[str], method: str = "pearson",
                labels: dict[str, str] | None = None) -> AnalysisResult:
    if method not in ("pearson", "spearman"):
        raise AnalysisError("Method must be 'pearson' or 'spearman'.")
    if len(columns) < 2:
        raise AnalysisError("Select at least two variables.")
    require_columns(df, columns)
    labels = labels or {}
    data = pd.DataFrame({c: numeric(df[c]) for c in columns})
    pairs = []
    for a, b in itertools.combinations(columns, 2):
        sub = data[[a, b]].dropna()
        n = len(sub)
        if n < 5 or sub[a].nunique() < 2 or sub[b].nunique() < 2:
            continue
        if method == "pearson":
            r, p = stats.pearsonr(sub[a], sub[b])
        else:
            r, p = stats.spearmanr(sub[a], sub[b])
        pairs.append({"x": a, "y": b, "r": float(r), "p": float(p), "n": n, "effect_label": label_r(float(r))})
    if not pairs:
        raise AnalysisError("Not enough complete, varying data to compute correlations.")
    adjusted = holm_adjust([pr["p"] for pr in pairs])
    for pr, adj in zip(pairs, adjusted, strict=True):
        pr["p_holm"] = adj

    matrix = {a: {b: (1.0 if a == b else None) for b in columns} for a in columns}
    for pr in pairs:
        matrix[pr["x"]][pr["y"]] = pr["r"]
        matrix[pr["y"]][pr["x"]] = pr["r"]

    non_normal = []
    if method == "pearson":
        for c in columns:
            values = data[c].dropna()
            if 8 <= len(values) <= 5000 and stats.shapiro(values).pvalue < 0.05 and abs(stats.skew(values)) > 1:
                non_normal.append(c)
    n_min = min(pr["n"] for pr in pairs)
    checks = [
        Check("Linearity", OK if method == "spearman" else WARNING,
              "Spearman's rho captures any monotonic relation." if method == "spearman"
              else "Pearson's r measures linear association only; inspect scatter plots for curved patterns."),
        Check("Distribution shape", WARNING if non_normal else OK,
              f"Strongly skewed, non-normal: {', '.join(non_normal)}. Consider Spearman's rho." if non_normal
              else "No strongly skewed variables detected." if method == "pearson" else "Rank-based; no normality needed."),
        Check("Multiple comparisons", WARNING if len(pairs) > 5 else OK,
              f"{len(pairs)} tests were run; Holm-adjusted p-values are reported to limit false positives."),
        Check("Sample size", OK if n_min >= 30 else WARNING, f"Smallest pairwise n = {n_min}."),
    ]
    significant = sorted((p for p in pairs if p["p_holm"] < 0.05), key=lambda p: -abs(p["r"]))
    symbol = "r" if method == "pearson" else "rho"
    evidence = [
        EvidenceCandidate(
            key=f"corr:{p['x']}:{p['y']}",
            title=f"{labels.get(p['x'], p['x'])} and {labels.get(p['y'], p['y'])}",
            statement=(f"{labels.get(p['x'], p['x'])} and {labels.get(p['y'], p['y'])} are "
                       f"{'positively' if p['r'] > 0 else 'negatively'} correlated ({symbol} = {fmt_num(p['r'])}, "
                       f"Holm-adjusted {fmt_p(p['p_holm'])}, n = {p['n']}, {p['effect_label']} effect)."),
            n=p["n"], effect_size=p["r"], effect_label=p["effect_label"], p_value=p["p_holm"],
            strength=strength_from_test(p["p_holm"], p["n"], p["effect_label"]),
            value={"r": p["r"], "p_unadjusted": p["p"]},
        )
        for p in significant[:10]
    ]
    summary = (f"{len(significant)} of {len(pairs)} correlations remain significant after Holm correction."
               if pairs else "No correlations computed.")
    chart = {"type": "heatmap", "title": "Correlation matrix", "rows": columns, "cols": columns,
             "data": [[matrix[a][b] for b in columns] for a in columns], "domain": [-1, 1],
             "labels": [labels.get(c, c) for c in columns]}
    return AnalysisResult(
        method="correlation",
        title=f"Correlation ({method})",
        n=int(np.max([p["n"] for p in pairs])),
        result={"method": method, "pairs": pairs, "matrix": matrix},
        assumptions=checks,
        summary=summary,
        limitations=[ASSOCIATION_NOTE],
        evidence=evidence,
        charts=[chart],
    )
