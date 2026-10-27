"""Voice of the customer: map review sentences to journey stages, score emotion, find pain points."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from ..analytics.common import (
    OK,
    WARNING,
    AnalysisError,
    AnalysisResult,
    Check,
    EvidenceCandidate,
    fmt_num,
    fmt_pct,
    require_columns,
)
from ..analytics.sentiment import score_text
from .templates import PAIN_THEMES, template

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_RE.split(text or "") if len(s.strip()) > 3]


def classify_stage(sentence: str, stages: list[dict[str, Any]]) -> str | None:
    low = sentence.lower()
    best, best_hits = None, 0
    for stage in stages:
        hits = sum(1 for kw in stage.get("keywords", []) if re.search(r"\b" + re.escape(kw) + r"\b", low))
        if hits > best_hits:
            best, best_hits = stage["key"], hits
    return best


def theme_for(sentence: str) -> str:
    low = sentence.lower()
    for keywords, label in PAIN_THEMES:
        if any(k in low for k in keywords):
            return label
    return "Other issues"


def analyze(df: pd.DataFrame, text_column: str, template_key: str = "tourism", rating_column: str | None = None,
            group_column: str | None = None) -> AnalysisResult:
    require_columns(df, [text_column] + [c for c in (rating_column, group_column) if c])
    tpl = template(template_key)
    stages = tpl["stages"]
    order = [s["key"] for s in stages]
    names = {s["key"]: s["name"] for s in stages}
    texts = df[text_column].where(df[text_column].notna())
    docs = [(i, str(t)) for i, t in texts.items() if isinstance(t, str) and t.strip()]
    n_docs = len(docs)
    if n_docs < 10:
        raise AnalysisError("Voice-of-customer analysis needs at least 10 texts.")

    rows = []
    for idx, text in docs:
        for sentence in split_sentences(text):
            stage = classify_stage(sentence, stages)
            s = score_text(sentence)
            rows.append({"doc": idx, "sentence": sentence, "stage": stage, "compound": s["compound"], "label": s["label"]})
    frame = pd.DataFrame(rows)
    mapped = frame[frame["stage"].notna()]
    coverage = mapped["doc"].nunique() / n_docs

    stage_rows = []
    for key in order:
        sub = mapped[mapped["stage"] == key]
        mentions = int(sub["doc"].nunique())
        neg = sub[sub["label"] == "negative"]
        pos = sub[sub["label"] == "positive"]
        stage_rows.append({
            "key": key, "name": names[key], "mentions": mentions, "mention_share": mentions / n_docs,
            "emotion": float(sub["compound"].mean()) if len(sub) else None,
            "negative_share": float((sub["label"] == "negative").mean()) if len(sub) else None,
            "positive_share": float((sub["label"] == "positive").mean()) if len(sub) else None,
            "negative_mentions": int(neg["doc"].nunique()),
            "top_positive": pos.drop_duplicates("sentence").nlargest(2, "compound")["sentence"].tolist(),
            "top_negative": neg.drop_duplicates("sentence").nsmallest(2, "compound")["sentence"].tolist(),
        })

    negatives = mapped[mapped["label"] == "negative"].copy()
    negatives["theme"] = negatives["sentence"].map(theme_for)
    themes = sorted(negatives["theme"].unique().tolist())
    heatmap = [[int(negatives[(negatives["stage"] == key) & (negatives["theme"] == th)]["doc"].nunique()) for th in themes]
               for key in order]

    pain_points = []
    for (stage, theme), grp in negatives.groupby(["stage", "theme"]):
        mentions = int(grp["doc"].nunique())
        if mentions < 2:
            continue
        severity = float(np.clip(-grp["compound"].mean(), 0, 1))
        frequency = mentions / n_docs
        quotes = grp.drop_duplicates("sentence").nsmallest(3, "compound")["sentence"].tolist()
        pain_points.append({"stage": stage, "stage_name": names[stage], "theme": theme,
                            "title": f"{names[stage]}: {theme}", "mentions": mentions, "frequency": frequency,
                            "severity": severity, "quotes": quotes})
    pain_points.sort(key=lambda p: -(p["frequency"] * p["severity"]))

    rating_link = None
    if rating_column:
        per_doc = frame.groupby("doc")["compound"].mean()
        ratings = pd.to_numeric(df.loc[per_doc.index, rating_column], errors="coerce")
        valid = ratings.notna()
        if valid.sum() >= 10:
            rating_link = float(np.corrcoef(per_doc[valid], ratings[valid])[0, 1])

    evidence = []
    for p in pain_points[:6]:
        evidence.append(EvidenceCandidate(
            key=f"voc:{p['stage']}:{p['theme']}", title=p["title"],
            statement=(f"{p['mentions']} of {n_docs} reviews ({fmt_pct(p['frequency'])}) describe a negative {p['stage_name'].lower()} "
                       f"experience about {p['theme'].lower()}, for example: \"{p['quotes'][0][:160]}\""),
            n=n_docs, strength="moderate" if p["mentions"] >= 15 else "weak", effect_size=p["severity"], effect_label="severity",
            value={"stage": p["stage"], "theme": p["theme"], "mentions": p["mentions"], "severity": p["severity"]},
        ))
    best = max((s for s in stage_rows if s["emotion"] is not None and s["mentions"] >= 5), key=lambda s: s["emotion"], default=None)
    if best:
        evidence.append(EvidenceCandidate(
            key=f"voc:peak:{best['key']}", title=f"Emotional high point: {best['name']}",
            statement=(f"The most positive stage is {best['name']} (mean sentiment {fmt_num(best['emotion'])}, "
                       f"{best['mentions']} reviews), for example: \"{(best['top_positive'] or [''])[0][:160]}\""),
            n=n_docs, strength="moderate" if best["mentions"] >= 15 else "weak",
            value={"stage": best["key"], "emotion": best["emotion"]},
        ))
    checks = [
        Check("Stage coverage", OK if coverage >= 0.7 else WARNING,
              f"{fmt_pct(coverage)} of reviews mention at least one stage keyword."),
        Check("Keyword mapping", WARNING, "Stages are assigned by bilingual keyword rules; review ambiguous sentences."),
        Check("Review sample bias", WARNING, "Online reviews over-represent very satisfied and very dissatisfied visitors."),
    ]
    if rating_link is not None:
        checks.append(Check("Agreement with star ratings", OK if rating_link >= 0.3 else WARNING,
                            f"Correlation between review sentiment and rating = {fmt_num(rating_link)}.", value=rating_link))
    worst = min((s for s in stage_rows if s["emotion"] is not None and s["mentions"] >= 5), key=lambda s: s["emotion"], default=None)
    summary = (f"{n_docs} reviews mapped to the {tpl['name']} journey ({fmt_pct(coverage)} coverage). "
               + (f"Lowest point: {worst['name']} (mean sentiment {fmt_num(worst['emotion'])}). " if worst else "")
               + (f"Top pain point: {pain_points[0]['title']} ({pain_points[0]['mentions']} reviews)." if pain_points else ""))
    languages = Counter("id" if re.search(r"\b(yang|dan|di|sangat|banget)\b", t.lower()) else "en" for _, t in docs)
    return AnalysisResult(
        method="journey_voc",
        title=f"Voice of the customer: {tpl['name']}",
        n=n_docs,
        result={"template": template_key, "stages": stage_rows, "pain_points": pain_points,
                "heatmap": {"stages": [names[k] for k in order], "stage_keys": order, "themes": themes, "counts": heatmap},
                "coverage": coverage, "rating_correlation": rating_link, "languages": dict(languages),
                "unmapped_examples": frame[frame["stage"].isna()]["sentence"].head(5).tolist()},
        assumptions=checks,
        summary=summary,
        limitations=["Keyword rules can miss implicit references; an LLM-assisted classification is used when configured."],
        evidence=evidence,
        charts=[{"type": "emotion_curve", "title": "Emotion by journey stage",
                 "data": [{"label": s["name"], "value": s["emotion"], "n": s["mentions"]} for s in stage_rows]},
                {"type": "heatmap", "title": "Friction heatmap (negative mentions)", "rows": [names[k] for k in order],
                 "cols": themes, "data": heatmap}],
    )
