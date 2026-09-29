"""Column type inference and profiling for uploaded datasets."""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from ..jsonutil import to_jsonable

ID_NAMES = re.compile(r"^(id|respondent(_?id)?|resp(_?id)?|uuid|case(_?id)?|record(_?id)?|no|nomor)$", re.I)
PRICE_NAMES = re.compile(r"(price|harga|wtp|_rp$|^rp_|vw_|gg_|tarif|biaya|budget)", re.I)
DATE_NAMES = re.compile(r"(date|time|tanggal|waktu|timestamp|submitted)", re.I)
RATING_NAMES = re.compile(r"(recommend|nps|rating|rate|score|likely|satisf|puas|nilai|skor)", re.I)
TEXT_NAMES = re.compile(r"(comment|review|feedback|open|text|komentar|ulasan|saran|alasan|why|reason)", re.I)
YES_TOKENS = {"yes", "y", "ya", "iya", "true", "1", "setuju", "mau", "bersedia"}
NO_TOKENS = {"no", "n", "tidak", "tdk", "false", "0", "tidak mau", "tidak bersedia", "gak", "nggak"}

TYPES = ("numeric", "likert", "binary", "categorical", "text", "price", "id", "datetime")


def infer_type(series: pd.Series, name: str) -> str:
    s = series.dropna()
    if s.empty:
        return "categorical"
    n_unique = s.nunique()
    unique_ratio = n_unique / max(len(s), 1)

    if ID_NAMES.match(name.strip()) and unique_ratio > 0.95:
        return "id"

    as_num = pd.to_numeric(s, errors="coerce")
    numeric_share = float(as_num.notna().mean())

    if numeric_share >= 0.98:
        values = as_num.dropna()
        if PRICE_NAMES.search(name):
            return "price"
        uniq = set(np.unique(values))
        if uniq <= {0, 1} and len(uniq) == 2:
            return "binary"
        is_int = bool(np.all(np.isclose(values, np.round(values))))
        lo, hi = values.quantile(0.01), values.quantile(0.99)  # robust to a stray typo
        if is_int and n_unique <= 12 and lo >= 0 and hi <= 11:
            if lo >= 1 and hi <= 7 and n_unique >= 3:
                return "likert"
            if lo >= 0 and hi <= 10 and n_unique >= 3 and RATING_NAMES.search(name):
                return "likert"
        if ID_NAMES.match(name.strip()) and unique_ratio > 0.95:
            return "id"
        return "numeric"

    lowered = s.astype(str).str.strip().str.lower()
    if n_unique == 2 and set(lowered.unique()) <= (YES_TOKENS | NO_TOKENS):
        return "binary"
    if DATE_NAMES.search(name):
        parsed = pd.to_datetime(s, errors="coerce", format="mixed")
        if parsed.notna().mean() > 0.9:
            return "datetime"
    avg_len = float(lowered.str.len().mean())
    if TEXT_NAMES.search(name) and avg_len > 15:
        return "text"
    if avg_len > 40 or (unique_ratio > 0.6 and avg_len > 20):
        return "text"
    if n_unique == 2:
        return "binary"
    return "categorical"


def profile_column(series: pd.Series, name: str, inferred: str | None = None) -> dict[str, Any]:
    inferred = inferred or infer_type(series, name)
    total = len(series)
    missing = int(series.isna().sum() + (series.astype(str).str.strip() == "").sum() if total else 0)
    missing = min(missing, total)
    profile: dict[str, Any] = {
        "name": name,
        "inferred_type": inferred,
        "n": total - missing,
        "missing": missing,
        "missing_share": (missing / total) if total else 0.0,
        "unique": int(series.nunique(dropna=True)),
    }
    if inferred in ("numeric", "likert", "price", "binary"):
        values = pd.to_numeric(series, errors="coerce").dropna()
        if inferred == "binary" and values.empty:
            lowered = series.dropna().astype(str).str.strip().str.lower()
            values = lowered.map(lambda v: 1.0 if v in YES_TOKENS else 0.0 if v in NO_TOKENS else np.nan).dropna()
        if not values.empty:
            profile.update(
                {
                    "mean": float(values.mean()),
                    "sd": float(values.std(ddof=1)) if len(values) > 1 else None,
                    "min": float(values.min()),
                    "max": float(values.max()),
                    "median": float(values.median()),
                }
            )
    if inferred in ("categorical", "binary", "likert"):
        counts = series.dropna().astype(str).value_counts().head(12)
        profile["top_values"] = [{"value": k, "count": int(v)} for k, v in counts.items()]
    if inferred == "text":
        texts = series.dropna().astype(str)
        profile["avg_length"] = float(texts.str.len().mean()) if not texts.empty else 0.0
        profile["examples"] = texts.head(3).tolist()
    return to_jsonable(profile)


def profile_frame(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [profile_column(df[c], str(c)) for c in df.columns]


def to_binary(series: pd.Series, positive: str | None = None) -> pd.Series:
    """Map a binary-like column to 0/1 floats. ``positive`` names the value that counts as 1."""
    if pd.api.types.is_numeric_dtype(series):
        values = pd.to_numeric(series, errors="coerce")
        uniq = sorted(values.dropna().unique())
        if positive is not None:
            return (values == float(positive)).astype(float).where(values.notna())
        if set(uniq) <= {0, 1}:
            return values.astype(float)
        if len(uniq) == 2:
            return (values == uniq[1]).astype(float).where(values.notna())
        raise ValueError("Column is not binary.")
    lowered = series.astype(str).str.strip().str.lower().where(series.notna())
    if positive is not None:
        return (lowered == str(positive).strip().lower()).astype(float).where(lowered.notna())
    mapped = lowered.map(lambda v: 1.0 if v in YES_TOKENS else 0.0 if v in NO_TOKENS else np.nan)
    if mapped.notna().sum() == lowered.notna().sum():
        return mapped
    uniq = sorted(lowered.dropna().unique())
    if len(uniq) == 2:
        return (lowered == uniq[1]).astype(float).where(lowered.notna())
    raise ValueError("Column is not binary.")
