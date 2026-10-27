"""Price research: Van Westendorp Price Sensitivity Meter, Gabor-Granger demand, and WTP at a target price.

Van Westendorp curves follow the empirical-CDF definitions used by the R package
``pricesensitivitymeter`` (Alletsee): "too cheap" and "cheap" are 1 - F(p), "expensive" and
"too expensive" are F(p). Intersections are located on the grid of observed prices and refined by
linear interpolation.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .common import (
    OK,
    WARNING,
    AnalysisError,
    AnalysisResult,
    Check,
    EvidenceCandidate,
    fmt_pct,
    numeric,
    require_columns,
    strength_from_proportion,
    wilson_ci,
)
from .profiling import to_binary

STATED_PREFERENCE_LIMITATION = (
    "Stated willingness to pay usually overstates real purchasing (hypothetical bias). Validate the chosen price "
    "with a behavioral test such as a pre-sale page or an A/B price test."
)


def money(x: float | None, currency: str = "IDR") -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    if currency == "IDR":
        return "Rp " + f"{x:,.0f}".replace(",", ".")
    return f"{currency} {x:,.2f}"


def _ecdf(values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    values = np.sort(values)
    return np.searchsorted(values, grid, side="right") / len(values)


def _intersection(grid: np.ndarray, f1: np.ndarray, f2: np.ndarray) -> float | None:
    diff = f1 - f2
    for i in range(len(grid)):
        if diff[i] == 0:
            return float(grid[i])
        if i + 1 < len(grid) and np.sign(diff[i]) != np.sign(diff[i + 1]) and diff[i + 1] != 0:
            d0, d1 = diff[i], diff[i + 1]
            return float(grid[i] + (grid[i + 1] - grid[i]) * d0 / (d0 - d1))
    return None


def van_westendorp(df: pd.DataFrame, too_cheap: str, cheap: str, expensive: str, too_expensive: str,
                   target_price: float | None = None, currency: str = "IDR") -> AnalysisResult:
    require_columns(df, [too_cheap, cheap, expensive, too_expensive])
    raw = pd.DataFrame({
        "tc": numeric(df[too_cheap]), "c": numeric(df[cheap]),
        "e": numeric(df[expensive]), "te": numeric(df[too_expensive]),
    }).dropna()
    n_complete = len(raw)
    valid_mask = (raw["tc"] <= raw["c"]) & (raw["c"] <= raw["e"]) & (raw["e"] <= raw["te"])
    data = raw[valid_mask]
    n = len(data)
    n_invalid = n_complete - n
    if n < 20:
        raise AnalysisError("Van Westendorp needs at least 20 respondents with consistent answers to all four questions.")

    grid = np.unique(np.concatenate([data[c].to_numpy() for c in ("tc", "c", "e", "te")]))
    too_cheap_curve = 1 - _ecdf(data["tc"].to_numpy(), grid)
    cheap_curve = 1 - _ecdf(data["c"].to_numpy(), grid)
    expensive_curve = _ecdf(data["e"].to_numpy(), grid)
    too_expensive_curve = _ecdf(data["te"].to_numpy(), grid)
    not_cheap = 1 - cheap_curve
    not_expensive = 1 - expensive_curve

    pmc = _intersection(grid, too_cheap_curve, not_cheap)
    pme = _intersection(grid, too_expensive_curve, not_expensive)
    opp = _intersection(grid, too_cheap_curve, too_expensive_curve)
    ipp = _intersection(grid, cheap_curve, expensive_curve)

    target = None
    if target_price is not None:
        tp = float(target_price)
        share_too_cheap = float((data["tc"] > tp).mean())
        share_too_expensive = float((data["te"] <= tp).mean())
        share_expensive = float((data["e"] <= tp).mean())
        share_cheap = float((data["c"] > tp).mean())
        acceptable = 1 - share_too_cheap - share_too_expensive
        lo, hi = wilson_ci(int(round(acceptable * n)), n)
        target = {"price": tp, "too_cheap": share_too_cheap, "cheap": share_cheap, "expensive": share_expensive,
                  "too_expensive": share_too_expensive, "acceptable": acceptable, "ci_low": lo, "ci_high": hi,
                  "within_range": bool(pmc is not None and pme is not None and pmc <= tp <= pme)}

    checks = [
        Check("Logical consistency", OK if n_invalid / max(n_complete, 1) <= 0.1 else WARNING,
              f"{n_invalid} of {n_complete} respondents gave inconsistent answers and were excluded.",
              value=float(n_invalid)),
        Check("Sample size", OK if n >= 100 else WARNING,
              f"n = {n}; curves become stable at about 100 or more respondents."),
        Check("Offer understood", WARNING,
              "Assumes respondents saw a clear description of the offer before the price questions."),
    ]
    evidence: list[EvidenceCandidate] = []
    range_text = f"{money(pmc, currency)} to {money(pme, currency)}"
    evidence.append(EvidenceCandidate(
        key="vw:range", title="Acceptable price range (Van Westendorp)",
        statement=(f"The acceptable price range is {range_text}, with an optimal price point of {money(opp, currency)} "
                   f"and an indifference price point of {money(ipp, currency)} (n = {n})."),
        n=n, strength="moderate" if n >= 100 else "weak",
        value={"pmc": pmc, "pme": pme, "opp": opp, "ipp": ipp},
    ))
    if target:
        evidence.append(EvidenceCandidate(
            key="vw:target", title=f"Reaction to {money(target['price'], currency)}",
            statement=(f"At {money(target['price'], currency)}, {fmt_pct(target['too_expensive'])} of respondents call it too "
                       f"expensive and {fmt_pct(target['too_cheap'])} too cheap, so {fmt_pct(target['acceptable'])} find it "
                       f"acceptable (95% CI {fmt_pct(target['ci_low'])} to {fmt_pct(target['ci_high'])}, n = {n}); the price is "
                       f"{'inside' if target['within_range'] else 'outside'} the acceptable range."),
            n=n, ci_low=target["ci_low"], ci_high=target["ci_high"],
            strength=strength_from_proportion(n, target["ci_low"], target["ci_high"]), value=target,
        ))
    step = max(1, len(grid) // 60)
    curve_points = [
        {"price": float(grid[i]), "too_cheap": float(too_cheap_curve[i]), "cheap": float(cheap_curve[i]),
         "expensive": float(expensive_curve[i]), "too_expensive": float(too_expensive_curve[i]),
         "not_cheap": float(not_cheap[i]), "not_expensive": float(not_expensive[i])}
        for i in range(0, len(grid), step)
    ]
    summary = evidence[0].statement
    return AnalysisResult(
        method="van_westendorp",
        title="Van Westendorp Price Sensitivity Meter",
        n=n,
        result={"pmc": pmc, "pme": pme, "opp": opp, "ipp": ipp, "n_invalid": n_invalid, "target": target,
                "curves": curve_points, "currency": currency,
                "columns": {"too_cheap": too_cheap, "cheap": cheap, "expensive": expensive, "too_expensive": too_expensive}},
        assumptions=checks,
        summary=summary,
        limitations=[STATED_PREFERENCE_LIMITATION,
                     "Van Westendorp shows price perceptions, not purchase probability; pair it with Gabor-Granger or a purchase question."],
        evidence=evidence,
        charts=[{"type": "price_curves", "title": "Price sensitivity curves", "data": curve_points,
                 "markers": {"PMC": pmc, "OPP": opp, "IPP": ipp, "PME": pme}, "target": target_price, "currency": currency}],
    )


def gabor_granger(df: pd.DataFrame, price_columns: dict[str, str], threshold: float | None = None,
                  target_price: float | None = None, currency: str = "IDR") -> AnalysisResult:
    """``price_columns`` maps a price (as text or number) to the column holding purchase intent at that price.

    Binary columns (yes/no) count "yes". Scale columns count answers at or above ``threshold``
    (default: the top two boxes of the observed scale).
    """
    if len(price_columns) < 3:
        raise AnalysisError("Gabor-Granger needs purchase intent at three or more price points.")
    require_columns(df, list(price_columns.values()))
    points = []
    for price_text, col in sorted(price_columns.items(), key=lambda kv: float(kv[0])):
        price = float(price_text)
        series = df[col]
        try:
            willing = to_binary(series).dropna()
            rule = "yes"
        except ValueError:
            values = numeric(series).dropna()
            cut = threshold if threshold is not None else float(values.max()) - 1
            willing = (values >= cut).astype(float)
            rule = f">= {cut:g}"
        n = int(willing.notna().sum())
        k = int(willing.sum())
        lo, hi = wilson_ci(k, n)
        share = k / n if n else float("nan")
        points.append({"price": price, "column": col, "n": n, "willing": k, "share": share, "ci_low": lo, "ci_high": hi,
                       "revenue_index": price * share, "rule": rule})
    non_monotone = [points[i + 1]["price"] for i in range(len(points) - 1) if points[i + 1]["share"] > points[i]["share"] + 1e-9]
    for i in range(len(points) - 1):
        p1, p2 = points[i], points[i + 1]
        q1, q2 = p1["share"], p2["share"]
        if q1 + q2 > 0:
            p1["arc_elasticity_to_next"] = ((q2 - q1) / ((q2 + q1) / 2)) / ((p2["price"] - p1["price"]) / ((p2["price"] + p1["price"]) / 2))
    best = max(points, key=lambda p: p["revenue_index"])
    n_min = min(p["n"] for p in points)
    checks = [
        Check("Monotone demand", OK if not non_monotone else WARNING,
              "Willingness falls as price rises." if not non_monotone
              else f"Willingness rises at {', '.join(money(p, currency) for p in non_monotone)}: check question order and wording."),
        Check("Sample size per price", OK if n_min >= 100 else WARNING, f"Smallest n per price point = {n_min}."),
        Check("Price order effects", WARNING, "Asking prices in a fixed order anchors answers; randomize or descend from high to low."),
    ]
    evidence = [EvidenceCandidate(
        key="gg:revenue_max", title="Revenue-maximizing tested price",
        statement=(f"Among tested prices, {money(best['price'], currency)} maximizes expected revenue per potential customer "
                   f"({fmt_pct(best['share'])} willing to buy, 95% CI {fmt_pct(best['ci_low'])} to {fmt_pct(best['ci_high'])})."),
        n=best["n"], ci_low=best["ci_low"], ci_high=best["ci_high"],
        strength=strength_from_proportion(best["n"], best["ci_low"], best["ci_high"]),
        value={"price": best["price"], "share": best["share"]},
    )]
    if target_price is not None:
        match = min(points, key=lambda p: abs(p["price"] - float(target_price)))
        evidence.append(EvidenceCandidate(
            key="gg:target", title=f"Purchase intent at {money(match['price'], currency)}",
            statement=(f"At {money(match['price'], currency)}, {fmt_pct(match['share'])} of respondents say they would buy "
                       f"(95% CI {fmt_pct(match['ci_low'])} to {fmt_pct(match['ci_high'])}, n = {match['n']})."),
            n=match["n"], ci_low=match["ci_low"], ci_high=match["ci_high"],
            strength=strength_from_proportion(match["n"], match["ci_low"], match["ci_high"]),
            value={"price": match["price"], "share": match["share"]},
        ))
    return AnalysisResult(
        method="gabor_granger",
        title="Gabor-Granger demand curve",
        n=max(p["n"] for p in points),
        result={"points": points, "revenue_max_price": best["price"], "currency": currency,
                "price_response": [{"price": p["price"], "share": p["share"]} for p in points]},
        assumptions=checks,
        summary=evidence[0].statement,
        limitations=[STATED_PREFERENCE_LIMITATION, "Revenue index ignores costs and capacity; use the Strategy Simulator for profit."],
        evidence=evidence,
        charts=[{"type": "demand_curve", "title": "Demand and revenue by price", "data": points, "currency": currency,
                 "target": target_price}],
    )


def wtp_at_price(df: pd.DataFrame, column: str, price: float, group: str | None = None,
                 positive: str | None = None, currency: str = "IDR") -> AnalysisResult:
    require_columns(df, [column] + ([group] if group else []))
    try:
        y = to_binary(df[column], positive)
    except ValueError as exc:
        raise AnalysisError(f"'{column}' must be a yes/no question.") from exc
    valid = y.dropna()
    n = len(valid)
    if n < 10:
        raise AnalysisError("Need at least 10 answers.")
    k = int(valid.sum())
    lo, hi = wilson_ci(k, n)
    share = k / n
    groups = []
    if group:
        frame = pd.DataFrame({"y": y, "g": df[group].astype(str).where(df[group].notna())}).dropna()
        for g, sub in frame.groupby("g"):
            gk, gn = int(sub["y"].sum()), len(sub)
            glo, ghi = wilson_ci(gk, gn)
            groups.append({"group": g, "n": gn, "share": gk / gn, "ci_low": glo, "ci_high": ghi})
        groups.sort(key=lambda r: -r["share"])
    statement = (f"{fmt_pct(share)} of respondents say they would pay {money(price, currency)} "
                 f"(95% CI {fmt_pct(lo)} to {fmt_pct(hi)}, n = {n}).")
    evidence = [EvidenceCandidate(key=f"wtp:{column}", title=f"Willingness to pay {money(price, currency)}",
                                  statement=statement, n=n, ci_low=lo, ci_high=hi,
                                  strength=strength_from_proportion(n, lo, hi), value={"share": share, "price": price})]
    if len(groups) >= 2:
        top, bottom = groups[0], groups[-1]
        evidence.append(EvidenceCandidate(
            key=f"wtp:{column}:by:{group}", title=f"Willingness to pay by {group}",
            statement=(f"Willingness to pay {money(price, currency)} ranges from {fmt_pct(bottom['share'])} ({bottom['group']}, "
                       f"n = {bottom['n']}) to {fmt_pct(top['share'])} ({top['group']}, n = {top['n']})."),
            n=n, strength="weak" if min(top["n"], bottom["n"]) < 50 else "moderate", value={"groups": groups},
        ))
    return AnalysisResult(
        method="wtp",
        title=f"Willingness to pay {money(price, currency)}",
        n=n,
        result={"column": column, "price": price, "share": share, "ci_low": lo, "ci_high": hi, "groups": groups,
                "currency": currency},
        assumptions=[
            Check("Sample size", OK if n >= 100 else WARNING, f"n = {n}; margin of error about {fmt_pct((hi - lo) / 2)}."),
            Check("Representative sample", WARNING, "Shares generalize only if the sample matches the target market."),
        ],
        summary=statement,
        limitations=[STATED_PREFERENCE_LIMITATION],
        evidence=evidence,
        charts=[{"type": "bar", "title": f"Would pay {money(price, currency)}", "format": "percent",
                 "data": ([{"label": g["group"], "value": g["share"], "low": g["ci_low"], "high": g["ci_high"]} for g in groups]
                          or [{"label": "All", "value": share, "low": lo, "high": hi}])}],
    )
