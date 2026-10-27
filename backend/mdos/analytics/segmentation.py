"""k-means segmentation with a stated objective, stability checks, profiles and personas."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from .common import (
    NOT_APPLICABLE,
    OK,
    WARNING,
    AnalysisError,
    AnalysisResult,
    Check,
    EvidenceCandidate,
    fmt_num,
    fmt_pct,
    numeric,
    require_columns,
)
from .profiling import infer_type

MIN_OBJECTIVE_CHARS = 15


def _name_segment(z: pd.Series, labels: dict[str, str]) -> str:
    """Deterministic descriptive name from the two most distinctive variables."""
    top = z.reindex(z.abs().sort_values(ascending=False).index)[:2]
    parts = []
    for var, value in top.items():
        if abs(value) < 0.25:
            continue
        parts.append(f"{'High' if value > 0 else 'Low'} {labels.get(var, var)}")
    return " / ".join(parts) if parts else "Average profile"


def segment(df: pd.DataFrame, variables: list[str], objective: str, rationale: str, k: int | None = None,
            profile_columns: list[str] | None = None, text_column: str | None = None, seed: int = 42,
            labels: dict[str, str] | None = None) -> AnalysisResult:
    # Quality gate from the specification: no segmentation without an objective and variable rationale.
    if len((objective or "").strip()) < MIN_OBJECTIVE_CHARS or len((rationale or "").strip()) < MIN_OBJECTIVE_CHARS:
        raise AnalysisError("Segmentation needs a stated objective and a rationale for the chosen variables.")
    if len(variables) < 2:
        raise AnalysisError("Select at least two segmentation variables.")
    labels = labels or {}
    profile_columns = [c for c in (profile_columns or []) if c not in variables]
    require_columns(df, variables + profile_columns + ([text_column] if text_column else []))
    data = pd.DataFrame({v: numeric(df[v]) for v in variables}).dropna()
    n = len(data)
    if n < 30:
        raise AnalysisError("Segmentation needs at least 30 complete cases.")
    Z = StandardScaler().fit_transform(data.to_numpy())

    candidates = [k] if k else list(range(2, min(6, n // 10) + 1))
    if not candidates or (k is not None and (k < 2 or k > 10)):
        raise AnalysisError("Choose between 2 and 10 segments.")
    evaluation = []
    fits = {}
    for kk in candidates:
        model = KMeans(n_clusters=kk, n_init=20, random_state=seed).fit(Z)
        sil = float(silhouette_score(Z, model.labels_)) if kk > 1 else float("nan")
        evaluation.append({"k": kk, "silhouette": sil, "inertia": float(model.inertia_)})
        fits[kk] = model
    best_k = k or max(evaluation, key=lambda e: (round(e["silhouette"], 3), -e["k"]))["k"]
    model = fits[best_k]
    assignments = model.labels_

    aris = []
    for s in range(1, 6):
        alt = KMeans(n_clusters=best_k, n_init=20, random_state=seed + s * 101).fit(Z)
        aris.append(adjusted_rand_score(assignments, alt.labels_))
    stability = float(np.mean(aris))

    frame = df.loc[data.index].copy()
    frame["__segment"] = assignments
    overall_mean = data.mean()
    overall_sd = data.std(ddof=1).replace(0, np.nan)
    segments = []
    for seg_id in range(best_k):
        members = frame[frame["__segment"] == seg_id]
        means = data.loc[members.index].mean()
        z = ((means - overall_mean) / overall_sd).fillna(0)
        name = _name_segment(z, labels)
        profile = {"means": means.to_dict(), "z": z.to_dict(), "descriptors": {}}
        for col in profile_columns:
            kind = infer_type(df[col], col)
            if kind in ("numeric", "likert", "price", "binary"):
                vals = numeric(members[col])
                if vals.notna().any():
                    profile["descriptors"][col] = {"type": "numeric", "mean": float(vals.mean())}
            else:
                counts = members[col].dropna().astype(str).value_counts(normalize=True)
                if not counts.empty:
                    profile["descriptors"][col] = {"type": "categorical", "top": counts.index[0],
                                                   "share": float(counts.iloc[0]),
                                                   "distribution": {k2: float(v) for k2, v in counts.head(5).items()}}
        quote = None
        if text_column:
            texts = members[text_column].dropna().astype(str)
            texts = texts[texts.str.len() > 25]
            if not texts.empty:
                quote = texts.iloc[int(np.argmin(np.abs(texts.str.len() - texts.str.len().median())))]
        persona = _persona(name, len(members) / n, z, profile["descriptors"], labels, quote)
        segments.append({"id": seg_id, "name": name, "size": int(len(members)), "share": len(members) / n,
                         "profile": profile, "persona": persona})
    segments.sort(key=lambda s: -s["size"])

    smallest = min(s["share"] for s in segments)
    best_sil = next(e["silhouette"] for e in evaluation if e["k"] == best_k)
    checks = [
        Check("Objective and variable rationale", OK, f"Objective: {objective.strip()[:160]}"),
        Check("Separation (silhouette)", OK if best_sil >= 0.25 else WARNING,
              f"Silhouette = {fmt_num(best_sil)} ({'reasonable' if best_sil >= 0.25 else 'weak'} structure; .25 or higher is reasonable).",
              value=best_sil),
        Check("Stability across random starts", OK if stability >= 0.8 else WARNING,
              f"Mean adjusted Rand index across 5 re-runs = {fmt_num(stability)} (0.80 or higher is stable).", value=stability),
        Check("Segment size", OK if smallest >= 0.05 else WARNING,
              f"Smallest segment holds {fmt_pct(smallest)} of the sample (5% or more is actionable)."),
        Check("Variable scaling", OK, "Variables were standardized so each contributes equally."),
        Check("Cluster shape", NOT_APPLICABLE, "k-means favors compact, similarly sized clusters; latent class analysis is planned for Phase 2."),
    ]
    statement = (f"{best_k} segments were identified (silhouette {fmt_num(best_sil)}, stability {fmt_num(stability)}, n = {n}): "
                 + "; ".join(f"{s['name']} ({fmt_pct(s['share'], 0)})" for s in segments) + ".")
    return AnalysisResult(
        method="segmentation",
        title=f"Segmentation ({best_k} segments)",
        n=n,
        result={"k": best_k, "evaluation": evaluation, "segments": segments, "variables": variables,
                "objective": objective, "rationale": rationale, "stability_ari": stability, "seed": seed,
                "assignments": {int(i): int(a) for i, a in zip(data.index, assignments, strict=True)}},
        assumptions=checks,
        summary=statement,
        limitations=["Segments depend on the chosen variables and k; validate them against behavior before targeting."],
        evidence=[EvidenceCandidate(key="segmentation", title="Customer segments", statement=statement, n=n,
                                    effect_size=best_sil, effect_label="silhouette",
                                    strength="moderate" if best_sil >= 0.25 and stability >= 0.8 else "weak",
                                    value={"k": best_k, "segments": [{"name": s["name"], "share": s["share"]} for s in segments]})],
        charts=[{"type": "segment_profiles", "title": "Segment profiles (z-scores)",
                 "variables": [labels.get(v, v) for v in variables],
                 "segments": [{"name": s["name"], "share": s["share"], "z": [s["profile"]["z"][v] for v in variables]}
                              for s in segments]}],
    )


def _persona(name: str, share: float, z: pd.Series, descriptors: dict, labels: dict[str, str], quote: str | None) -> dict:
    values = [labels.get(v, v) for v, s in z.sort_values(ascending=False).items() if s >= 0.3][:3]
    concerns = [labels.get(v, v) for v, s in z.sort_values().items() if s <= -0.3][:3]
    who = [f"{labels.get(col, col)}: {d['top']} ({fmt_pct(d['share'], 0)})" for col, d in descriptors.items()
           if d.get("type") == "categorical"][:4]
    facts = [f"{labels.get(col, col)}: {fmt_num(d['mean'])}" for col, d in descriptors.items() if d.get("type") == "numeric"][:4]
    return {
        "name": name,
        "share": share,
        "who": who,
        "values": values,
        "concerns": concerns,
        "facts": facts,
        "quote": quote,
        "note": "Persona built from segment statistics; the quote is a real response from a segment member.",
    }
