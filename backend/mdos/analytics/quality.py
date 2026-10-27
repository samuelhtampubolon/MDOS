"""Data quality diagnostics for survey and text datasets.

Each issue carries a suggested cleaning operation so the Data Cleaning agent can propose a plan that a
person approves. Nothing here modifies data.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd

from ..jsonutil import to_jsonable
from .profiling import infer_type

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+?62|0)8[0-9\-\s]{7,13}")
PSEUDONYM_RE = re.compile(r"[0-9a-f]{12}")  # output of the pseudonymize cleaning operation
PII_NAMES = re.compile(
    r"(e-?mail|phone|telp|telepon|hp$|^hp|whatsapp|^wa$|^wa_|nama|^name$|full_?name|address|alamat|nik|ktp|passport)",
    re.I,
)
DURATION_NAMES = re.compile(r"(duration|durasi|time_?taken|seconds|elapsed|lama_isi)", re.I)
VW_KEYS = {
    "too_cheap": re.compile(r"(too_?cheap|terlalu_?murah)", re.I),
    "cheap": re.compile(r"(^|_)(cheap|bargain|murah)$", re.I),
    "expensive": re.compile(r"(^|_)(expensive|mahal)$", re.I),
    "too_expensive": re.compile(r"(too_?expensive|terlalu_?mahal)", re.I),
}


def likert_batteries(columns: dict[str, str]) -> dict[str, list[str]]:
    """Group Likert columns into batteries by their alphabetic prefix (ci1, ci2 -> 'ci')."""
    groups: dict[str, list[str]] = defaultdict(list)
    for name, kind in columns.items():
        if kind != "likert":
            continue
        prefix = re.sub(r"[_\-]?\d+$", "", name)
        groups[prefix].append(name)
    return {k: sorted(v) for k, v in groups.items() if len(v) >= 2}


def detect_vw_columns(df: pd.DataFrame) -> dict[str, str] | None:
    found: dict[str, str] = {}
    for col in df.columns:
        low = str(col).lower()
        for key in ("too_cheap", "too_expensive", "cheap", "expensive"):
            if key in found:
                continue
            if VW_KEYS[key].search(low):
                if key in ("cheap", "expensive") and ("too" in low or "terlalu" in low):
                    continue
                found[key] = str(col)
                break
    return found if len(found) == 4 else None


def diagnose(
    df: pd.DataFrame,
    column_types: dict[str, str] | None = None,
    scales: dict[str, tuple[float, float]] | None = None,
    attention_checks: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run all quality checks. ``column_types`` overrides inference; ``scales`` gives Likert ranges."""
    column_types = dict(column_types or {})
    for col in df.columns:
        column_types.setdefault(str(col), infer_type(df[col], str(col)))
    scales = scales or {}
    attention_checks = attention_checks or {}
    n_rows = len(df)
    issues: list[dict[str, Any]] = []
    flagged_rows: dict[str, set[int]] = defaultdict(set)

    def add(check: str, severity: str, message: str, suggestion: str, count: int = 0,
            column: str | None = None, rows: list[int] | None = None, operation: dict | None = None) -> None:
        issues.append(
            {
                "id": f"{check}:{column or 'all'}",
                "check": check,
                "severity": severity,
                "column": column,
                "count": int(count),
                "rows": [int(r) for r in (rows or [])][:500],
                "message": message,
                "suggestion": suggestion,
                "operation": operation,
            }
        )

    # 1. Missing data
    for col in df.columns:
        series = df[col]
        blank = series.isna() | (series.astype(str).str.strip() == "")
        share = float(blank.mean()) if n_rows else 0.0
        if share > 0.05 and column_types.get(str(col)) != "text":
            severity = "high" if share > 0.20 else "medium"
            add("missing", severity, f"{share:.0%} of values are missing in '{col}'.",
                "Check whether the question was optional or skipped by logic. Analyses use listwise deletion.",
                count=int(blank.sum()), column=str(col))

    # 2. Duplicates
    dup_mask = df.duplicated(keep="first")
    if dup_mask.any():
        rows = list(np.where(dup_mask)[0])
        add("duplicate_rows", "high", f"{len(rows)} rows are exact duplicates of an earlier row.",
            "Drop duplicates (keeps the first occurrence).", count=len(rows), rows=rows,
            operation={"op": "drop_duplicates"})
    id_cols = [c for c, t in column_types.items() if t == "id"]
    for col in id_cols:
        dup_ids = df[col].duplicated(keep=False) & df[col].notna()
        if dup_ids.any():
            add("duplicate_ids", "high", f"{int(dup_ids.sum())} rows share an ID in '{col}'.",
                "Investigate repeated submissions; keep the first complete response.",
                count=int(dup_ids.sum()), column=col, rows=list(np.where(dup_ids)[0]))

    # 3. Straight-lining across multi-item Likert batteries
    batteries = likert_batteries(column_types)
    likert_cols = [c for c, t in column_types.items() if t == "likert"]
    battery_cols = sorted({c for cols in batteries.values() for c in cols})
    if len(battery_cols) >= 6:
        block = df[battery_cols].apply(pd.to_numeric, errors="coerce")
        complete = block.notna().sum(axis=1) >= 6
        zero_var = (block.std(axis=1, ddof=0) == 0) & complete
        rows = list(np.where(zero_var)[0])
        if rows:
            for r in rows:
                flagged_rows["straightlining"].add(int(r))
            add("straightlining", "medium",
                f"{len(rows)} respondents gave the identical answer to every item in the Likert batteries ({len(battery_cols)} items).",
                "Straight-lining often signals low effort. Consider excluding these respondents.",
                count=len(rows), rows=rows,
                operation={"op": "drop_rows", "rows": rows, "reason": "straight-lining across all Likert items"})

    # 4. Speeders
    duration_cols = [c for c in df.columns if DURATION_NAMES.search(str(c))]
    for col in duration_cols[:1]:
        values = pd.to_numeric(df[col], errors="coerce")
        median = float(values.median()) if values.notna().any() else float("nan")
        if median and not np.isnan(median):
            fast = values < (median / 3)
            rows = list(np.where(fast.fillna(False))[0])
            if rows:
                for r in rows:
                    flagged_rows["speeders"].add(int(r))
                add("speeders", "medium",
                    f"{len(rows)} respondents finished in under a third of the median time ({median:.0f}).",
                    "Speeders rarely read questions carefully. Consider excluding them.",
                    count=len(rows), column=str(col), rows=rows,
                    operation={"op": "drop_rows", "rows": rows, "reason": f"completion time below {median / 3:.0f}"})

    # 5. Attention checks
    for col, expected in attention_checks.items():
        if col not in df.columns:
            continue
        values = df[col].astype(str).str.strip().str.lower()
        failed = values != str(expected).strip().lower()
        rows = list(np.where(failed & df[col].notna())[0])
        if rows:
            for r in rows:
                flagged_rows["attention"].add(int(r))
            add("attention_check", "high", f"{len(rows)} respondents failed the attention check '{col}'.",
                "Exclude respondents who failed the attention check.", count=len(rows), column=str(col), rows=rows,
                operation={"op": "drop_rows", "rows": rows, "reason": f"failed attention check {col}"})

    # 6. Out-of-range Likert values (scale from metadata, else inferred per battery)
    battery_of = {c: cols for cols in batteries.values() for c in cols}
    for col in likert_cols:
        if col not in scales and col not in battery_of:
            continue  # a single rating item has no reference scale to compare against
        values = pd.to_numeric(df[col], errors="coerce")
        lo, hi = scales.get(col) or _infer_scale(df, battery_of[col])
        bad = (values < lo) | (values > hi)
        if bad.any():
            add("out_of_range", "high", f"{int(bad.sum())} values in '{col}' fall outside the {lo:g} to {hi:g} scale.",
                "Set out-of-range values to missing.", count=int(bad.sum()), column=col,
                rows=list(np.where(bad)[0]),
                operation={"op": "set_out_of_range_missing", "column": col, "min": lo, "max": hi})

    # 7. Outliers in numeric and price columns
    for col, kind in column_types.items():
        if kind not in ("numeric", "price"):
            continue
        values = pd.to_numeric(df[col], errors="coerce")
        clean = values.dropna()
        if len(clean) < 10:
            continue
        q1, q3 = np.percentile(clean, [25, 75])
        iqr = q3 - q1
        if iqr <= 0:
            continue
        extreme = (values < q1 - 3 * iqr) | (values > q3 + 3 * iqr)
        if extreme.any():
            add("outliers", "low", f"{int(extreme.sum())} extreme values in '{col}' (beyond 3 x IQR).",
                "Check for typing errors (for example an extra zero in a price). Valid extremes can stay.",
                count=int(extreme.sum()), column=col, rows=list(np.where(extreme)[0]),
                operation={"op": "winsorize", "column": col, "lower": 0.01, "upper": 0.99})

    # 8. Personal data
    pii_cols: list[str] = []
    for col in df.columns:
        name = str(col)
        sample = df[col].dropna().astype(str).head(200)
        if not len(sample) or sample.str.fullmatch(PSEUDONYM_RE).all():
            continue  # empty or already pseudonymized
        by_value = sample.str.contains(EMAIL_RE).mean() > 0.3 or sample.str.contains(PHONE_RE).mean() > 0.3
        if PII_NAMES.search(name) or by_value:
            pii_cols.append(name)
    if pii_cols:
        add("personal_data", "high", f"Possible personal data in: {', '.join(pii_cols)}.",
            "Drop or pseudonymize these columns before analysis and sharing.", count=len(pii_cols),
            operation={"op": "pseudonymize", "columns": pii_cols})

    # 9. Van Westendorp logical consistency
    vw = detect_vw_columns(df)
    if vw:
        block = df[[vw["too_cheap"], vw["cheap"], vw["expensive"], vw["too_expensive"]]].apply(
            pd.to_numeric, errors="coerce"
        )
        tc, c, e, te = (block.iloc[:, i] for i in range(4))
        complete = block.notna().all(axis=1)
        bad = complete & ((tc > c) | (c > e) | (e > te))
        rows = list(np.where(bad)[0])
        if rows:
            for r in rows:
                flagged_rows["price_inconsistent"].add(int(r))
            add("price_inconsistency", "medium",
                f"{len(rows)} respondents gave illogical Van Westendorp answers (for example 'too cheap' above 'expensive').",
                "Van Westendorp analysis excludes these respondents automatically; you may also drop them.",
                count=len(rows), rows=rows,
                operation={"op": "drop_rows", "rows": rows, "reason": "inconsistent Van Westendorp price answers"})

    # 10. Constant columns
    for col in df.columns:
        if df[col].nunique(dropna=True) == 1 and n_rows > 5:
            add("constant", "low", f"'{col}' has the same value in every row.",
                "Constant columns carry no information for analysis.", column=str(col),
                operation={"op": "drop_columns", "columns": [str(col)]})

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda i: (severity_rank[i["severity"]], i["check"]))
    all_flagged = set().union(*flagged_rows.values()) if flagged_rows else set()
    score = _quality_score(issues, n_rows)
    return to_jsonable(
        {
            "n_rows": n_rows,
            "n_cols": int(df.shape[1]),
            "column_types": column_types,
            "likert_batteries": batteries,
            "van_westendorp_columns": vw,
            "personal_data_columns": pii_cols,
            "issues": issues,
            "flagged_respondents": len(all_flagged),
            "flagged_share": (len(all_flagged) / n_rows) if n_rows else 0.0,
            "quality_score": score,
        }
    )


def _infer_scale(df: pd.DataFrame, battery: list[str]) -> tuple[float, float]:
    """Infer a battery's scale from its items' typical range, snapping to common scales (1-5, 1-7, 0-10)."""
    lows, highs = [], []
    for col in battery:
        values = pd.to_numeric(df[col], errors="coerce").dropna()
        if values.empty:
            continue
        lows.append(values.quantile(0.02))
        highs.append(values.quantile(0.98))
    lo = float(np.median(lows)) if lows else 1.0
    hi = float(np.median(highs)) if highs else 5.0
    for scale in ((1.0, 5.0), (1.0, 7.0), (0.0, 10.0), (1.0, 10.0)):
        if lo >= scale[0] and hi <= scale[1]:
            return scale
    return (lo, hi)


def _quality_score(issues: list[dict[str, Any]], n_rows: int) -> int:
    """0-100 summary for the dashboard; transparent weighting documented in the methods reference."""
    penalty = 0.0
    for issue in issues:
        weight = {"high": 8, "medium": 4, "low": 1}[issue["severity"]]
        share = issue["count"] / n_rows if n_rows and issue["count"] else 0.0
        penalty += weight * (0.5 + min(share * 5, 1.5))
    return int(max(0, round(100 - penalty)))
