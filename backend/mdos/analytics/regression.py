"""OLS and logistic regression with assumption checks and associational interpretation."""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import roc_auc_score
from statsmodels.stats.diagnostic import het_breuschpagan, linear_reset
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson, jarque_bera

from .common import (
    ASSOCIATION_NOTE,
    OK,
    VIOLATED,
    WARNING,
    AnalysisError,
    AnalysisResult,
    Check,
    EvidenceCandidate,
    fmt_num,
    fmt_p,
    label_f2,
    label_odds_ratio,
    numeric,
    require_columns,
    strength_from_test,
)
from .profiling import to_binary


@dataclass
class Design:
    y: pd.Series
    X: pd.DataFrame  # without constant
    term_variable: dict[str, str]  # term -> source variable
    term_level: dict[str, str | None]
    categorical: dict[str, str]  # variable -> reference level
    n_dropped: int


def build_design(df: pd.DataFrame, dv: str, predictors: list[str], *, binary_dv: bool = False,
                 positive: str | None = None, force_categorical: list[str] | None = None) -> Design:
    if not predictors:
        raise AnalysisError("Select at least one predictor.")
    if dv in predictors:
        raise AnalysisError("The outcome cannot also be a predictor.")
    require_columns(df, [dv, *predictors])
    force_categorical = set(force_categorical or [])
    frame = pd.DataFrame(index=df.index)
    if binary_dv:
        try:
            frame["__y"] = to_binary(df[dv], positive)
        except ValueError as exc:
            raise AnalysisError(f"'{dv}' is not a binary variable.") from exc
    else:
        frame["__y"] = numeric(df[dv])
    kinds: dict[str, str] = {}
    for p in predictors:
        coerced = pd.to_numeric(df[p], errors="coerce")
        share = coerced.notna().sum() / max(df[p].notna().sum(), 1)
        if p not in force_categorical and share >= 0.98:
            frame[p] = coerced.astype(float)
            kinds[p] = "numeric"
        else:
            frame[p] = df[p].astype("object").where(df[p].notna())
            kinds[p] = "categorical"
    before = len(frame)
    frame = frame.dropna()
    n_dropped = before - len(frame)

    columns, term_variable, term_level, categorical = {}, {}, {}, {}
    for p in predictors:
        if kinds[p] == "numeric":
            columns[p] = frame[p]
            term_variable[p], term_level[p] = p, None
        else:
            levels = frame[p].astype(str)
            counts = levels.value_counts()
            if len(counts) < 2:
                raise AnalysisError(f"Predictor '{p}' has fewer than two categories after removing missing data.")
            reference = str(counts.index[0])
            categorical[p] = reference
            for level in sorted(counts.index):
                if level == reference:
                    continue
                term = f"{p}[{level}]"
                columns[term] = (levels == level).astype(float)
                term_variable[term], term_level[term] = p, level
    X = pd.DataFrame(columns, index=frame.index)
    constant_terms = [c for c in X.columns if X[c].nunique() < 2]
    if constant_terms:
        raise AnalysisError(f"Predictor(s) without variation: {', '.join(constant_terms)}.")
    return Design(y=frame["__y"], X=X, term_variable=term_variable, term_level=term_level,
                  categorical=categorical, n_dropped=n_dropped)


def _vif(X: pd.DataFrame) -> dict[str, float]:
    if X.shape[1] < 2:
        return {c: 1.0 for c in X.columns}
    exog = sm.add_constant(X, has_constant="add").to_numpy()
    out = {}
    for i, col in enumerate(X.columns, start=1):
        with np.errstate(divide="ignore", invalid="ignore"):
            out[col] = float(variance_inflation_factor(exog, i))
    return out


def _term_label(term: str, design: Design, labels: dict[str, str]) -> str:
    var = design.term_variable[term]
    level = design.term_level[term]
    base = labels.get(var, var)
    if level is None:
        return base
    return f"{base} = {level} (vs {design.categorical[var]})"


def ols(df: pd.DataFrame, dv: str, predictors: list[str], *, robust: str = "auto",
        labels: dict[str, str] | None = None, force_categorical: list[str] | None = None) -> AnalysisResult:
    labels = labels or {}
    design = build_design(df, dv, predictors, force_categorical=force_categorical)
    n, k = len(design.y), design.X.shape[1]
    if n < k + 10:
        raise AnalysisError(f"Too few complete cases ({n}) for {k} predictor terms.")
    exog = sm.add_constant(design.X, has_constant="add")
    base = sm.OLS(design.y, exog).fit()

    bp_lm, bp_p, _, _ = het_breuschpagan(base.resid, exog)
    use_robust = bool(robust == "HC3" or (robust == "auto" and bp_p < 0.05))
    fit = sm.OLS(design.y, exog).fit(cov_type="HC3") if use_robust else base

    try:
        reset_p = float(linear_reset(base, power=2, use_f=True).pvalue)
    except Exception:  # noqa: BLE001 - diagnostic is optional on degenerate designs
        reset_p = float("nan")
    jb_stat, jb_p, _, _ = jarque_bera(base.resid)
    dw = float(durbin_watson(base.resid))
    vifs = _vif(design.X)
    cooks = base.get_influence().cooks_distance[0]
    influential = int((cooks > 4 / n).sum())
    sd_y = float(design.y.std(ddof=1))

    # Partial f-squared per source variable (drop all its terms and refit).
    partial_f2: dict[str, float] = {}
    r2_full = float(base.rsquared)
    for var in dict.fromkeys(design.term_variable.values()):
        keep = [t for t in design.X.columns if design.term_variable[t] != var]
        r2_reduced = float(sm.OLS(design.y, sm.add_constant(design.X[keep], has_constant="add")).fit().rsquared) if keep else 0.0
        partial_f2[var] = max(0.0, (r2_full - r2_reduced) / max(1e-12, 1 - r2_full))

    ci = fit.conf_int()
    rows = []
    for term in exog.columns:
        is_const = term == "const"
        sd_x = float(design.X[term].std(ddof=1)) if not is_const else None
        beta = float(fit.params[term]) * sd_x / sd_y if (sd_x and sd_y) else None
        rows.append({
            "term": "Intercept" if is_const else term,
            "label": "Intercept" if is_const else _term_label(term, design, labels),
            "variable": None if is_const else design.term_variable[term],
            "b": float(fit.params[term]), "se": float(fit.bse[term]),
            "t": float(fit.tvalues[term]), "p": float(fit.pvalues[term]),
            "ci_low": float(ci.loc[term, 0]), "ci_high": float(ci.loc[term, 1]),
            "beta": beta, "vif": None if is_const else vifs.get(term),
        })

    green_min = 50 + 8 * k
    max_vif = max(vifs.values()) if vifs else 1.0
    checks = [
        Check("Linearity (Ramsey RESET)", OK if (math.isnan(reset_p) or reset_p >= 0.05) else WARNING,
              f"RESET {fmt_p(reset_p)}." + ("" if (math.isnan(reset_p) or reset_p >= 0.05)
                                            else " Some non-linearity; consider transformations or polynomial terms."),
              value=None if math.isnan(reset_p) else reset_p),
        Check("Homoscedasticity (Breusch-Pagan)", OK if bp_p >= 0.05 else WARNING,
              f"Breusch-Pagan {fmt_p(bp_p)}." + (" Heteroscedasticity detected; HC3 robust standard errors are used."
                                                 if use_robust and bp_p < 0.05 else ""), value=float(bp_p)),
        Check("Normality of residuals (Jarque-Bera)",
              OK if jb_p >= 0.05 else (WARNING if n >= 100 else VIOLATED),
              f"Jarque-Bera {fmt_p(jb_p)}." + ("" if jb_p >= 0.05 else
                                               " With n of 100 or more, inference is robust to moderate non-normality."
                                               if n >= 100 else " Small sample: interpret p-values with caution."),
              value=float(jb_p)),
        Check("Multicollinearity (VIF)", OK if max_vif < 5 else (WARNING if max_vif < 10 else VIOLATED),
              f"Largest VIF = {fmt_num(max_vif)}." + ("" if max_vif < 5 else " Predictors overlap strongly; coefficients are unstable."),
              value=max_vif),
        Check("Independence of errors (Durbin-Watson)", OK if 1.5 <= dw <= 2.5 else WARNING,
              f"Durbin-Watson = {fmt_num(dw)} (1.5 to 2.5 is acceptable; relevant mainly for ordered data).", value=dw),
        Check("Sample size (Green, 1991)", OK if n >= green_min else WARNING,
              f"n = {n}; the rule of thumb for {k} terms is at least {green_min}.", value=float(n)),
        Check("Influential observations (Cook's distance)", OK if influential <= max(1, 0.05 * n) else WARNING,
              f"{influential} observations exceed Cook's D of 4/n.", value=float(influential)),
    ]
    f2_model = r2_full / max(1e-12, 1 - r2_full)
    dv_label = labels.get(dv, dv)
    evidence = [EvidenceCandidate(
        key=f"ols_model:{dv}", title=f"Model fit for {dv_label}",
        statement=(f"The predictors together account for {r2_full:.0%} of the variance in {dv_label} "
                   f"(R² = {fmt_num(r2_full)}, adjusted R² = {fmt_num(float(base.rsquared_adj))}, "
                   f"F({int(base.df_model)}, {int(base.df_resid)}) = {fmt_num(float(base.fvalue))}, "
                   f"{fmt_p(float(base.f_pvalue))}, n = {n})."),
        n=n, effect_size=f2_model, effect_label=label_f2(f2_model), p_value=float(base.f_pvalue),
        strength=strength_from_test(float(base.f_pvalue), n, label_f2(f2_model)),
        value={"r2": r2_full, "adj_r2": float(base.rsquared_adj), "f2": f2_model},
    )]
    for row in rows:
        if row["term"] == "Intercept":
            continue
        var = row["variable"]
        f2 = partial_f2.get(var, 0.0)
        others = [labels.get(v, v) for v in dict.fromkeys(design.term_variable.values()) if v != var]
        direction = "higher" if row["b"] > 0 else "lower"
        control = f", controlling for {', '.join(others)}" if others else ""
        if design.term_level[row["term"]] is None:
            text = (f"Higher {row['label']} is associated with {direction} {dv_label} "
                    f"(b = {fmt_num(row['b'], 3)}, 95% CI {fmt_num(row['ci_low'], 3)} to {fmt_num(row['ci_high'], 3)}, "
                    f"beta = {fmt_num(row['beta'])}, {fmt_p(row['p'])}{control}, n = {n}).")
        else:
            text = (f"{row['label']} is associated with {direction} {dv_label} "
                    f"(b = {fmt_num(row['b'], 3)}, 95% CI {fmt_num(row['ci_low'], 3)} to {fmt_num(row['ci_high'], 3)}, "
                    f"{fmt_p(row['p'])}{control}, n = {n}).")
        evidence.append(EvidenceCandidate(
            key=f"ols:{dv}:{row['term']}", title=f"{row['label']} and {dv_label}", statement=text, n=n,
            effect_size=f2, effect_label=label_f2(f2), p_value=row["p"], ci_low=row["ci_low"], ci_high=row["ci_high"],
            strength=strength_from_test(row["p"], n, label_f2(f2)),
            value={"b": row["b"], "beta": row["beta"], "partial_f2": f2},
        ))
    sig = [r for r in rows if r["term"] != "Intercept" and r["p"] < 0.05]
    summary = (f"OLS regression of {dv_label} on {len(predictors)} predictor(s): R² = {fmt_num(r2_full)}, "
               f"{len(sig)} term(s) significant at .05 (n = {n}{', robust SE' if use_robust else ''}).")
    chart = {"type": "coefficients", "title": f"Standardized coefficients for {dv_label}",
             "data": [{"label": r["label"], "value": r["beta"], "low": (r["ci_low"] * (r["beta"] / r["b"])) if r["b"] else None,
                       "high": (r["ci_high"] * (r["beta"] / r["b"])) if r["b"] else None, "p": r["p"]}
                      for r in rows if r["term"] != "Intercept" and r["beta"] is not None]}
    return AnalysisResult(
        method="regression_ols",
        title=f"Linear regression: {dv_label}",
        n=n,
        result={
            "dv": dv, "predictors": predictors, "coefficients": rows, "robust_se": use_robust,
            "r2": r2_full, "adj_r2": float(base.rsquared_adj), "f": float(base.fvalue), "f_p": float(base.f_pvalue),
            "df_model": int(base.df_model), "df_resid": int(base.df_resid), "rmse": float(np.sqrt(base.mse_resid)),
            "aic": float(base.aic), "bic": float(base.bic), "partial_f2": partial_f2,
            "reference_levels": design.categorical, "n_dropped": design.n_dropped,
        },
        assumptions=checks,
        summary=summary,
        warnings=[f"{design.n_dropped} rows with missing values were excluded (listwise deletion)."] if design.n_dropped else [],
        limitations=[ASSOCIATION_NOTE, "Coefficients assume the model includes the relevant variables (no omitted-variable bias)."],
        evidence=evidence,
        charts=[chart],
    )


def logistic(df: pd.DataFrame, dv: str, predictors: list[str], *, positive: str | None = None,
             labels: dict[str, str] | None = None, force_categorical: list[str] | None = None) -> AnalysisResult:
    labels = labels or {}
    design = build_design(df, dv, predictors, binary_dv=True, positive=positive, force_categorical=force_categorical)
    y = design.y
    n, k = len(y), design.X.shape[1]
    events = int(y.sum())
    non_events = n - events
    if min(events, non_events) < 5:
        raise AnalysisError("The outcome needs at least 5 cases in each category.")
    exog = sm.add_constant(design.X, has_constant="add")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            fit = sm.Logit(y, exog).fit(disp=0, maxiter=200)
        except Exception as exc:  # noqa: BLE001 - statsmodels raises several separation errors
            raise AnalysisError(f"Logistic model could not be estimated ({exc}). Check for perfect separation.") from exc
    converged = bool(fit.mle_retvals.get("converged", True))
    pred = fit.predict(exog)
    auc = float(roc_auc_score(y, pred))
    accuracy = float(((pred >= 0.5).astype(float) == y).mean())
    ci = fit.conf_int()
    rows = []
    for term in exog.columns:
        is_const = term == "const"
        b = float(fit.params[term])
        rows.append({
            "term": "Intercept" if is_const else term,
            "label": "Intercept" if is_const else _term_label(term, design, labels),
            "variable": None if is_const else design.term_variable[term],
            "b": b, "se": float(fit.bse[term]), "z": float(fit.tvalues[term]), "p": float(fit.pvalues[term]),
            "odds_ratio": math.exp(b), "or_low": math.exp(float(ci.loc[term, 0])), "or_high": math.exp(float(ci.loc[term, 1])),
        })
    epv = min(events, non_events) / max(k, 1)
    vifs = _vif(design.X)
    max_vif = max(vifs.values()) if vifs else 1.0
    huge = [r["term"] for r in rows if abs(r["b"]) > 10]
    checks = [
        Check("Events per variable", OK if epv >= 10 else WARNING,
              f"{epv:.1f} events per predictor term (10 or more recommended).", value=epv),
        Check("Multicollinearity (VIF)", OK if max_vif < 5 else (WARNING if max_vif < 10 else VIOLATED),
              f"Largest VIF = {fmt_num(max_vif)}.", value=max_vif),
        Check("Convergence and separation", OK if converged and not huge else VIOLATED,
              "Model converged." if converged and not huge else
              f"Possible (quasi-)separation: very large coefficients for {', '.join(huge) or 'some terms'}."),
        Check("Linearity of the logit", WARNING,
              "Assumed for continuous predictors; not tested in the MVP (Box-Tidwell is planned)."),
    ]
    dv_label = labels.get(dv, dv)
    evidence = [EvidenceCandidate(
        key=f"logit_model:{dv}", title=f"Model fit for {dv_label}",
        statement=(f"The model discriminates {'well' if auc >= 0.7 else 'modestly'} between outcomes "
                   f"(AUC = {fmt_num(auc)}, McFadden R² = {fmt_num(float(fit.prsquared))}, "
                   f"LR chi-square({int(fit.df_model)}) = {fmt_num(float(fit.llr))}, {fmt_p(float(fit.llr_pvalue))}, n = {n})."),
        n=n, p_value=float(fit.llr_pvalue), effect_size=auc, effect_label="auc",
        strength=strength_from_test(float(fit.llr_pvalue), n, "medium" if auc >= 0.7 else "small"),
        value={"auc": auc, "pseudo_r2": float(fit.prsquared), "accuracy": accuracy},
    )]
    for row in rows:
        if row["term"] == "Intercept":
            continue
        label = label_odds_ratio(row["odds_ratio"])
        text = (f"{row['label']} is associated with {fmt_num(row['odds_ratio'])} times the odds of {dv_label} "
                f"(OR = {fmt_num(row['odds_ratio'])}, 95% CI {fmt_num(row['or_low'])} to {fmt_num(row['or_high'])}, "
                f"{fmt_p(row['p'])}, n = {n}).")
        evidence.append(EvidenceCandidate(
            key=f"logit:{dv}:{row['term']}", title=f"{row['label']} and {dv_label}", statement=text, n=n,
            effect_size=row["odds_ratio"], effect_label=label, p_value=row["p"], ci_low=row["or_low"], ci_high=row["or_high"],
            strength=strength_from_test(row["p"], n, label), value={"odds_ratio": row["odds_ratio"], "b": row["b"]},
        ))
    summary = (f"Logistic regression of {dv_label} ({events} of {n} positive): AUC = {fmt_num(auc)}, "
               f"McFadden R² = {fmt_num(float(fit.prsquared))}.")
    chart = {"type": "coefficients", "title": f"Odds ratios for {dv_label}", "log_scale": True, "reference": 1,
             "data": [{"label": r["label"], "value": r["odds_ratio"], "low": r["or_low"], "high": r["or_high"], "p": r["p"]}
                      for r in rows if r["term"] != "Intercept"]}
    return AnalysisResult(
        method="regression_logistic",
        title=f"Logistic regression: {dv_label}",
        n=n,
        result={
            "dv": dv, "predictors": predictors, "coefficients": rows, "events": events, "auc": auc,
            "accuracy": accuracy, "pseudo_r2": float(fit.prsquared), "llr": float(fit.llr),
            "llr_p": float(fit.llr_pvalue), "converged": converged, "reference_levels": design.categorical,
            "n_dropped": design.n_dropped,
        },
        assumptions=checks,
        summary=summary,
        warnings=[f"{design.n_dropped} rows with missing values were excluded (listwise deletion)."] if design.n_dropped else [],
        limitations=[ASSOCIATION_NOTE],
        evidence=evidence,
        charts=[chart],
    )
