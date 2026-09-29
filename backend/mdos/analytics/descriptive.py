"""Descriptive statistics for numeric, Likert and categorical variables."""

from __future__ import annotations

import pandas as pd
from scipy import stats

from .common import (
    NOT_APPLICABLE,
    OK,
    WARNING,
    AnalysisResult,
    Check,
    EvidenceCandidate,
    fmt_num,
    fmt_pct,
    mean_ci,
    numeric,
    require_columns,
    strength_from_proportion,
    wilson_ci,
)
from .profiling import infer_type


def describe(df: pd.DataFrame, columns: list[str], column_types: dict[str, str] | None = None,
             labels: dict[str, str] | None = None) -> AnalysisResult:
    require_columns(df, columns)
    column_types = column_types or {}
    labels = labels or {}
    numeric_rows, categorical_tables = [], []
    evidence: list[EvidenceCandidate] = []
    charts = []
    n_total = len(df)

    for col in columns:
        kind = column_types.get(col) or infer_type(df[col], col)
        label = labels.get(col, col)
        if kind in ("numeric", "likert", "price"):
            values = numeric(df[col]).dropna().to_numpy()
            n = len(values)
            if n == 0:
                continue
            lo, hi = mean_ci(values)
            row = {
                "variable": col,
                "label": label,
                "type": kind,
                "n": n,
                "missing": n_total - n,
                "mean": float(values.mean()),
                "sd": float(values.std(ddof=1)) if n > 1 else None,
                "se": float(values.std(ddof=1) / n**0.5) if n > 1 else None,
                "ci_low": lo,
                "ci_high": hi,
                "median": float(pd.Series(values).median()),
                "min": float(values.min()),
                "max": float(values.max()),
                "q1": float(pd.Series(values).quantile(0.25)),
                "q3": float(pd.Series(values).quantile(0.75)),
                "skewness": float(stats.skew(values, bias=False)) if n > 2 else None,
                "kurtosis": float(stats.kurtosis(values, bias=False)) if n > 3 else None,
            }
            if kind == "likert":
                scale_max = values.max()
                top2 = float((values >= scale_max - 1).mean()) if scale_max >= 4 else None
                counts = pd.Series(values).value_counts().sort_index()
                row["top2_box"] = top2
                row["distribution"] = [{"value": float(k), "count": int(v), "share": v / n} for k, v in counts.items()]
            numeric_rows.append(row)
            evidence.append(
                EvidenceCandidate(
                    key=f"mean:{col}",
                    title=f"Average {label}",
                    statement=(f"Mean {label} = {fmt_num(row['mean'])} (SD {fmt_num(row['sd'])}, "
                               f"95% CI {fmt_num(lo)} to {fmt_num(hi)}, n = {n})."),
                    n=n,
                    ci_low=lo,
                    ci_high=hi,
                    strength="moderate" if n >= 100 else "weak",
                    value={"mean": row["mean"], "sd": row["sd"], "top2_box": row.get("top2_box")},
                )
            )
        else:
            series = df[col].dropna().astype(str)
            n = len(series)
            if n == 0:
                continue
            counts = series.value_counts()
            table = []
            for value, count in counts.items():
                lo, hi = wilson_ci(int(count), n)
                table.append({"value": value, "count": int(count), "share": count / n, "ci_low": lo, "ci_high": hi})
            categorical_tables.append({"variable": col, "label": label, "type": kind, "n": n,
                                       "missing": n_total - n, "frequencies": table})
            charts.append({"type": "bar", "title": label, "data": [{"label": t["value"], "value": t["share"]}
                                                                   for t in table[:12]], "format": "percent"})
            top = table[0]
            evidence.append(
                EvidenceCandidate(
                    key=f"share:{col}:{top['value']}",
                    title=f"Most common {label}",
                    statement=(f"{fmt_pct(top['share'])} of respondents answered '{top['value']}' for {label} "
                               f"(95% CI {fmt_pct(top['ci_low'])} to {fmt_pct(top['ci_high'])}, n = {n})."),
                    n=n,
                    ci_low=top["ci_low"],
                    ci_high=top["ci_high"],
                    strength=strength_from_proportion(n, top["ci_low"], top["ci_high"]),
                    value={"share": top["share"], "value": top["value"]},
                )
            )

    if numeric_rows:
        charts.insert(0, {"type": "bar", "title": "Means", "data": [
            {"label": r["label"], "value": r["mean"], "low": r["ci_low"], "high": r["ci_high"]} for r in numeric_rows
        ], "format": "number"})

    skewed = [r["variable"] for r in numeric_rows if r.get("skewness") is not None and abs(r["skewness"]) > 1]
    min_n = min([r["n"] for r in numeric_rows] + [t["n"] for t in categorical_tables] or [0])
    checks = [
        Check("Sample representativeness", NOT_APPLICABLE,
              "Cannot be tested statistically. Compare the sample profile with the target population."),
        Check("Confidence intervals for means", OK if min_n >= 30 else WARNING,
              "t-based intervals are reliable for n of 30 or more or for roughly normal data."
              if min_n >= 30 else f"Smallest n is {min_n}; intervals assume roughly normal data."),
        Check("Skewness", WARNING if skewed else OK,
              f"Strongly skewed: {', '.join(skewed)}. Report medians alongside means." if skewed
              else "No variable has |skewness| above 1."),
    ]
    summary = f"Descriptive statistics for {len(numeric_rows) + len(categorical_tables)} variables (n = {n_total})."
    return AnalysisResult(
        method="descriptive",
        title="Descriptive statistics",
        n=n_total,
        result={"numeric": numeric_rows, "categorical": categorical_tables},
        assumptions=checks,
        summary=summary,
        limitations=["Descriptive statistics summarize this sample only; they do not test hypotheses."],
        evidence=evidence,
        charts=charts,
    )
