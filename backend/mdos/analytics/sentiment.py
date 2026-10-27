"""Transparent bilingual lexicon sentiment with negation, intensifiers and contrast handling.

The compound score is normalized to -1..+1 with x / sqrt(x^2 + 15), the normalization used by VADER.
Each result lists the terms that produced it, so every label is explainable.
"""

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
import pandas as pd

from .common import (
    OK,
    WARNING,
    AnalysisError,
    AnalysisResult,
    Check,
    EvidenceCandidate,
    fmt_num,
    fmt_pct,
    mean_ci,
    require_columns,
    strength_from_proportion,
    wilson_ci,
)
from .lexicon import CONTRAST, INTENSIFIERS, NEGATIVE, NEGATORS, PHRASES, POSITIVE, POST_INTENSIFIERS

LEXICON = {**POSITIVE, **NEGATIVE}
TOKEN_RE = re.compile(r"[a-zA-ZÀ-ɏ]+(?:-[a-zA-Z]+)?|!")
NEGATION_SCALE = -0.74
THRESHOLD = 0.05


def _normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = text.replace("n't", " not").replace("’", "'")
    text = re.sub(r"(.)\1{2,}", r"\1\1", text)  # "bagusss" -> "baguss"
    return text


def _stem_id(token: str) -> str:
    """Light Indonesian clitic stripping so 'pemandangannya' matches 'pemandangan'."""
    for suffix in ("nya", "lah", "kah"):
        if token.endswith(suffix) and len(token) > len(suffix) + 3 and token[: -len(suffix)] in LEXICON:
            return token[: -len(suffix)]
    return token


def score_text(text: str) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        return {"compound": 0.0, "label": "neutral", "terms": []}
    norm = _normalize_text(text)
    terms: list[dict[str, Any]] = []
    total = 0.0
    consumed_spans: list[tuple[int, int]] = []
    for phrase, valence in PHRASES.items():
        for m in re.finditer(r"\b" + re.escape(phrase) + r"\b", norm):
            consumed_spans.append(m.span())
            terms.append({"term": phrase, "valence": valence, "position": m.start()})

    tokens = [(m.group(0), m.start()) for m in TOKEN_RE.finditer(norm)]
    words = [t for t, _ in tokens]
    contrast_index = next((i for i, w in enumerate(words) if w in CONTRAST), None)
    exclamations = min(words.count("!"), 3)

    for i, (word, pos) in enumerate(tokens):
        if word == "!" or any(a <= pos < b for a, b in consumed_spans):
            continue
        base = _stem_id(word)
        valence = LEXICON.get(base)
        if valence is None or valence == 0:
            continue
        scale = 1.0
        window = words[max(0, i - 3):i]
        for w in window:
            if w in INTENSIFIERS:
                scale *= INTENSIFIERS[w]
        if i + 1 < len(words) and words[i + 1] in POST_INTENSIFIERS:
            scale *= POST_INTENSIFIERS[words[i + 1]]
        negated = any(w in NEGATORS for w in window)
        v = valence * scale
        if negated:
            v *= NEGATION_SCALE
        if contrast_index is not None:
            v *= 1.5 if i > contrast_index else 0.5
        terms.append({"term": word, "valence": round(v, 3), "negated": negated, "position": pos})

    for t in terms:
        if "negated" not in t and contrast_index is not None:  # phrases also respect contrast
            phrase_token_index = len(TOKEN_RE.findall(norm[: t["position"]]))
            t["valence"] = round(t["valence"] * (1.5 if phrase_token_index > contrast_index else 0.5), 3)
    total = sum(t["valence"] for t in terms)
    if total and exclamations:
        total += math.copysign(0.292 * exclamations, total)
    compound = total / math.sqrt(total * total + 15) if total else 0.0
    label = "positive" if compound >= THRESHOLD else "negative" if compound <= -THRESHOLD else "neutral"
    terms.sort(key=lambda t: t["position"])
    return {"compound": round(compound, 4), "label": label,
            "terms": [{"term": t["term"], "valence": t["valence"], "negated": t.get("negated", False)} for t in terms]}


def sentiment(df: pd.DataFrame, text_column: str, group: str | None = None,
              labels: dict[str, str] | None = None) -> AnalysisResult:
    require_columns(df, [text_column] + ([group] if group else []))
    labels = labels or {}
    texts = df[text_column].where(df[text_column].notna())
    mask = texts.astype(str).str.strip().str.len() > 0
    frame = pd.DataFrame({"text": texts[mask].astype(str)})
    if group:
        frame["group"] = df.loc[frame.index, group].astype(str)
    n = len(frame)
    if n < 5:
        raise AnalysisError("Sentiment analysis needs at least 5 non-empty texts.")
    scored = frame["text"].map(score_text)
    frame["compound"] = scored.map(lambda s: s["compound"])
    frame["label"] = scored.map(lambda s: s["label"])
    frame["terms"] = scored.map(lambda s: s["terms"])
    counts = frame["label"].value_counts()
    shares = {lab: float(counts.get(lab, 0) / n) for lab in ("positive", "neutral", "negative")}
    mean = float(frame["compound"].mean())
    lo, hi = mean_ci(frame["compound"].to_numpy())
    no_terms = float((frame["terms"].map(len) == 0).mean())

    by_group = []
    if group:
        for g, sub in frame.groupby("group"):
            gn = len(sub)
            neg = int((sub["label"] == "negative").sum())
            glo, ghi = wilson_ci(neg, gn)
            by_group.append({"group": g, "n": gn, "mean": float(sub["compound"].mean()),
                             "positive": float((sub["label"] == "positive").mean()),
                             "negative": neg / gn, "negative_ci": [glo, ghi]})
        by_group.sort(key=lambda r: r["mean"])

    term_totals: dict[str, list[float]] = {}
    for ts in frame["terms"]:
        for t in ts:
            term_totals.setdefault(t["term"], []).append(t["valence"])
    top_pos = sorted(((k, len(v)) for k, v in term_totals.items() if np.mean(v) > 0), key=lambda kv: -kv[1])[:12]
    top_neg = sorted(((k, len(v)) for k, v in term_totals.items() if np.mean(v) < 0), key=lambda kv: -kv[1])[:12]
    examples = {
        "most_positive": frame.nlargest(3, "compound")[["text", "compound"]].to_dict(orient="records"),
        "most_negative": frame.nsmallest(3, "compound")[["text", "compound"]].to_dict(orient="records"),
    }
    neg_n = int(counts.get("negative", 0))
    nlo, nhi = wilson_ci(neg_n, n)
    label = labels.get(text_column, text_column)
    statement = (f"Of {n} texts in {label}, {fmt_pct(shares['positive'])} are positive, {fmt_pct(shares['neutral'])} neutral "
                 f"and {fmt_pct(shares['negative'])} negative (mean compound {fmt_num(mean)}, 95% CI {fmt_num(lo)} to {fmt_num(hi)}).")
    evidence = [EvidenceCandidate(key=f"sentiment:{text_column}", title=f"Sentiment of {label}", statement=statement, n=n,
                                  ci_low=nlo, ci_high=nhi, strength=strength_from_proportion(n, nlo, nhi),
                                  value={"shares": shares, "mean": mean})]
    if len(by_group) >= 2:
        worst, best = by_group[0], by_group[-1]
        evidence.append(EvidenceCandidate(
            key=f"sentiment:{text_column}:by:{group}", title=f"Sentiment by {labels.get(group, group)}",
            statement=(f"Sentiment is lowest for {worst['group']} (mean {fmt_num(worst['mean'])}, {fmt_pct(worst['negative'])} negative, "
                       f"n = {worst['n']}) and highest for {best['group']} (mean {fmt_num(best['mean'])}, n = {best['n']})."),
            n=n, strength="weak" if min(worst["n"], best["n"]) < 30 else "moderate", value={"by_group": by_group},
        ))
    checks = [
        Check("Lexicon coverage", OK if no_terms <= 0.4 else WARNING,
              f"{fmt_pct(no_terms)} of texts contain no sentiment-bearing words and are scored neutral."),
        Check("Sarcasm and context", WARNING, "Lexicon methods miss sarcasm and domain-specific meaning; review examples."),
        Check("Human validation", WARNING, "Validate on a hand-labeled sample of at least 100 texts before relying on small differences."),
    ]
    return AnalysisResult(
        method="sentiment",
        title=f"Sentiment: {label}",
        n=n,
        result={"shares": shares, "mean": mean, "ci": [lo, hi], "by_group": by_group, "top_positive_terms": top_pos,
                "top_negative_terms": top_neg, "examples": examples, "no_term_share": no_terms,
                "documents": [{"index": int(i), "compound": float(r.compound), "label": r.label}
                              for i, r in frame.iterrows()][:5000]},
        assumptions=checks,
        summary=statement,
        limitations=["Lexicon-based sentiment is approximate; an LLM-assisted pass can be enabled when an API key is configured."],
        evidence=evidence,
        charts=[{"type": "bar", "title": "Sentiment distribution", "format": "percent",
                 "data": [{"label": k.title(), "value": v} for k, v in shares.items()]}]
        + ([{"type": "bar", "title": f"Mean sentiment by {labels.get(group, group)}", "format": "number",
             "data": [{"label": g["group"], "value": g["mean"]} for g in by_group]}] if by_group else []),
    )
