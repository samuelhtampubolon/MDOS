"""Text analytics: tokenization, keywords, bigrams and NMF themes for English and Indonesian text."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer

from .common import (
    OK,
    WARNING,
    AnalysisError,
    AnalysisResult,
    Check,
    EvidenceCandidate,
    fmt_pct,
    require_columns,
)
from .lexicon import STOPWORDS, STOPWORDS_EN, STOPWORDS_ID

WORD_RE = re.compile(r"[a-zA-ZÀ-ɏ]{2,}")


def tokenize(text: str, keep_stopwords: bool = False) -> list[str]:
    if not isinstance(text, str):
        return []
    text = re.sub(r"https?://\S+", " ", text.lower())
    tokens = []
    for tok in WORD_RE.findall(text):
        for suffix in ("nya", "lah", "kah"):
            if tok.endswith(suffix) and len(tok) > len(suffix) + 3:
                tok = tok[: -len(suffix)]
                break
        if keep_stopwords or (tok not in STOPWORDS and len(tok) > 2):
            tokens.append(tok)
    return tokens


def detect_language(text: str) -> str:
    words = WORD_RE.findall(text.lower()) if isinstance(text, str) else []
    en = sum(w in STOPWORDS_EN for w in words)
    idn = sum(w in STOPWORDS_ID for w in words)
    if en == idn == 0:
        return "unknown"
    if en > 2 * idn:
        return "en"
    if idn > 2 * en:
        return "id"
    return "mixed"


def keywords(texts: list[str], top: int = 25) -> dict[str, Any]:
    unigrams: Counter[str] = Counter()
    bigrams: Counter[str] = Counter()
    doc_freq: Counter[str] = Counter()
    for t in texts:
        toks = tokenize(t)
        unigrams.update(toks)
        doc_freq.update(set(toks))
        bigrams.update(f"{a} {b}" for a, b in zip(toks, toks[1:], strict=False))
    n = max(len(texts), 1)
    return {
        "unigrams": [{"term": k, "count": v, "doc_share": doc_freq[k] / n} for k, v in unigrams.most_common(top)],
        "bigrams": [{"term": k, "count": v} for k, v in bigrams.most_common(top) if v >= 2],
    }


def themes(texts: list[str], n_topics: int = 5, seed: int = 42, top_terms: int = 8) -> dict[str, Any]:
    """NMF on TF-IDF. Returns topics with top terms, prevalence and representative documents."""
    if len(texts) < 10:
        raise AnalysisError("Theme extraction needs at least 10 texts.")
    vectorizer = TfidfVectorizer(tokenizer=tokenize, lowercase=False, token_pattern=None, ngram_range=(1, 2),
                                 min_df=2, max_df=0.85)
    try:
        X = vectorizer.fit_transform(texts)
    except ValueError as exc:
        raise AnalysisError("Not enough repeated vocabulary to extract themes.") from exc
    n_topics = int(max(2, min(n_topics, X.shape[1] - 1, len(texts) // 5)))
    model = NMF(n_components=n_topics, init="nndsvda", random_state=seed, max_iter=500)
    W = model.fit_transform(X)
    H = model.components_
    vocab = np.array(vectorizer.get_feature_names_out())
    dominant = W.argmax(axis=1)
    has_weight = W.max(axis=1) > 0
    topics = []
    for k in range(n_topics):
        order = np.argsort(H[k])[::-1][:top_terms]
        members = np.where((dominant == k) & has_weight)[0]
        reps = members[np.argsort(W[members, k])[::-1][:3]] if len(members) else []
        topics.append({
            "id": k,
            "label": " / ".join(vocab[order[:3]]),
            "terms": [{"term": vocab[i], "weight": float(H[k, i])} for i in order],
            "prevalence": float(len(members) / len(texts)),
            "documents": int(len(members)),
            "examples": [texts[i] for i in reps],
        })
    topics.sort(key=lambda t: -t["prevalence"])
    return {"topics": topics, "assignments": [int(d) if w else -1 for d, w in zip(dominant, has_weight, strict=True)],
            "vocabulary_size": int(X.shape[1])}


def text_themes(df: pd.DataFrame, text_column: str, n_topics: int = 5, seed: int = 42,
                labels: dict[str, str] | None = None) -> AnalysisResult:
    require_columns(df, [text_column])
    labels = labels or {}
    series = df[text_column].dropna().astype(str)
    series = series[series.str.strip().str.len() > 0]
    texts = series.tolist()
    n = len(texts)
    if n < 10:
        raise AnalysisError("Text analytics needs at least 10 non-empty texts.")
    kw = keywords(texts)
    th = themes(texts, n_topics=n_topics, seed=seed)
    langs = Counter(detect_language(t) for t in texts)
    label = labels.get(text_column, text_column)
    top_theme = th["topics"][0]
    statement = (f"The most common theme in {label} is '{top_theme['label']}' ({fmt_pct(top_theme['prevalence'])} of {n} texts); "
                 f"frequent terms include {', '.join(k['term'] for k in kw['unigrams'][:5])}.")
    evidence = [EvidenceCandidate(key=f"theme:{text_column}:{t['id']}", title=f"Theme: {t['label']}",
                                  statement=(f"'{t['label']}' appears as the main theme in {t['documents']} of {n} texts "
                                             f"({fmt_pct(t['prevalence'])}). Example: \"{t['examples'][0][:180]}\"" if t["examples"]
                                             else f"'{t['label']}' appears in {t['documents']} of {n} texts."),
                                  n=n, strength="moderate" if t["documents"] >= 20 else "weak",
                                  value={"terms": [x["term"] for x in t["terms"]], "prevalence": t["prevalence"]})
                for t in th["topics"] if t["documents"] > 0]
    checks = [
        Check("Corpus size", OK if n >= 50 else WARNING, f"{n} texts; themes stabilize with 50 or more."),
        Check("Language mix", OK, ", ".join(f"{k}: {v}" for k, v in langs.most_common())),
        Check("Theme labels", WARNING, "Labels are the top terms; a researcher should name and validate themes."),
    ]
    return AnalysisResult(
        method="text_themes",
        title=f"Themes: {label}",
        n=n,
        result={"keywords": kw, "themes": th["topics"], "languages": dict(langs), "vocabulary_size": th["vocabulary_size"]},
        assumptions=checks,
        summary=statement,
        limitations=["Topic models find co-occurring words, not meaning; interpret themes with the example quotes."],
        evidence=evidence,
        charts=[{"type": "bar", "title": "Theme prevalence", "format": "percent",
                 "data": [{"label": t["label"], "value": t["prevalence"]} for t in th["topics"]]},
                {"type": "bar", "title": "Top terms", "format": "number",
                 "data": [{"label": k["term"], "value": k["count"]} for k in kw["unigrams"][:15]]}],
    )
