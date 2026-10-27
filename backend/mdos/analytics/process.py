"""PROCESS-style mediation (Model 4) and moderation (Model 1), following Hayes (2022).

Estimation uses OLS. The indirect effect in Model 4 is tested with a percentile bootstrap confidence
interval; the seed is recorded so results are reproducible.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from .common import (
    ASSOCIATION_NOTE,
    NOT_APPLICABLE,
    OK,
    WARNING,
    AnalysisError,
    AnalysisResult,
    Check,
    EvidenceCandidate,
    fmt_num,
    fmt_p,
    numeric,
    require_columns,
)


def _frame(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    require_columns(df, cols)
    data = pd.DataFrame({c: numeric(df[c]) for c in cols}).dropna()
    for c in cols:
        if data[c].nunique() < 2:
            raise AnalysisError(f"'{c}' has no variation after removing missing values.")
    return data


def _ols(y: np.ndarray, X: np.ndarray):
    return sm.OLS(y, sm.add_constant(X, has_constant="add")).fit()


def mediation(df: pd.DataFrame, x: str, m: str, y: str, covariates: list[str] | None = None,
              n_boot: int = 5000, seed: int = 20260928, confidence: float = 0.95,
              labels: dict[str, str] | None = None) -> AnalysisResult:
    covariates = covariates or []
    labels = labels or {}
    if len({x, m, y}) < 3:
        raise AnalysisError("X, M and Y must be three different variables.")
    data = _frame(df, [x, m, y, *covariates])
    n = len(data)
    if n < 30:
        raise AnalysisError("Mediation needs at least 30 complete cases.")
    n_boot = int(min(max(n_boot, 1000), 20000))
    X = data[x].to_numpy()
    M = data[m].to_numpy()
    Y = data[y].to_numpy()
    C = data[covariates].to_numpy() if covariates else np.empty((n, 0))

    model_m = _ols(M, np.column_stack([X, C]))
    model_y = _ols(Y, np.column_stack([X, M, C]))
    model_c = _ols(Y, np.column_stack([X, C]))
    a, se_a, p_a = model_m.params[1], model_m.bse[1], model_m.pvalues[1]
    c_prime, se_cp, p_cp = model_y.params[1], model_y.bse[1], model_y.pvalues[1]
    b, se_b, p_b = model_y.params[2], model_y.bse[2], model_y.pvalues[2]
    c_total, se_c, p_c = model_c.params[1], model_c.bse[1], model_c.pvalues[1]
    indirect = a * b

    rng = np.random.default_rng(seed)
    design_m = np.column_stack([np.ones(n), X, C])
    design_y = np.column_stack([np.ones(n), X, M, C])
    boot = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        coef_m, *_ = np.linalg.lstsq(design_m[idx], M[idx], rcond=None)
        coef_y, *_ = np.linalg.lstsq(design_y[idx], Y[idx], rcond=None)
        boot[i] = coef_m[1] * coef_y[2]
    alpha = 1 - confidence
    ci_low, ci_high = np.percentile(boot, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    boot_se = float(boot.std(ddof=1))
    sobel_se = math.sqrt(b**2 * se_a**2 + a**2 * se_b**2)
    sobel_z = indirect / sobel_se if sobel_se > 0 else float("nan")
    sobel_p = float(2 * (1 - stats.norm.cdf(abs(sobel_z)))) if sobel_se > 0 else float("nan")
    sd_x, sd_y = float(np.std(X, ddof=1)), float(np.std(Y, ddof=1))
    std_indirect = indirect * sd_x / sd_y
    significant = not (ci_low <= 0 <= ci_high)
    prop_mediated = indirect / c_total if (c_total != 0 and np.sign(indirect) == np.sign(c_total)) else None

    lx, lm, ly = labels.get(x, x), labels.get(m, m), labels.get(y, y)
    if significant and p_cp < 0.05:
        pattern = "partial (complementary) mediation" if np.sign(c_prime) == np.sign(indirect) else "competitive mediation"
    elif significant:
        pattern = "indirect-only mediation"
    elif p_cp < 0.05:
        pattern = "direct effect only (no indirect effect)"
    else:
        pattern = "no effect detected"
    statement = (
        f"The indirect association of {lx} with {ly} through {lm} is {fmt_num(indirect, 3)} "
        f"({int(confidence * 100)}% bootstrap CI {fmt_num(ci_low, 3)} to {fmt_num(ci_high, 3)}, {n_boot} resamples, n = {n}); "
        f"the interval {'excludes' if significant else 'includes'} zero ({pattern})."
    )
    checks = [
        Check("Causal order X to M to Y", WARNING,
              "Mediation assumes X precedes M and M precedes Y. Survey data measured at one time cannot establish this."),
        Check("No unmeasured confounding", NOT_APPLICABLE,
              "Confounders of the X-M, M-Y and X-Y relations are assumed absent or controlled as covariates."),
        Check("Residual normality (Y model)", OK if stats.jarque_bera(model_y.resid).pvalue >= 0.05 or n >= 100 else WARNING,
              "The bootstrap interval does not assume a normal sampling distribution of the indirect effect."),
        Check("Sample size", OK if n >= 100 else WARNING, f"n = {n}; bootstrap tests perform better with 100 or more cases."),
    ]
    paths = [
        {"path": "a", "label": f"{lx} -> {lm}", "b": a, "se": se_a, "p": p_a},
        {"path": "b", "label": f"{lm} -> {ly} (controlling {lx})", "b": b, "se": se_b, "p": p_b},
        {"path": "c'", "label": f"{lx} -> {ly} direct", "b": c_prime, "se": se_cp, "p": p_cp},
        {"path": "c", "label": f"{lx} -> {ly} total", "b": c_total, "se": se_c, "p": p_c},
    ]
    return AnalysisResult(
        method="mediation",
        title=f"Mediation (PROCESS Model 4): {lx} -> {lm} -> {ly}",
        n=n,
        result={"x": x, "m": m, "y": y, "covariates": covariates, "paths": paths, "indirect": indirect,
                "boot_ci": [float(ci_low), float(ci_high)], "boot_se": boot_se, "n_boot": n_boot, "seed": seed,
                "sobel_z": sobel_z, "sobel_p": sobel_p, "standardized_indirect": std_indirect,
                "proportion_mediated": prop_mediated, "pattern": pattern,
                "r2_m": float(model_m.rsquared), "r2_y": float(model_y.rsquared)},
        assumptions=checks,
        summary=statement,
        limitations=[ASSOCIATION_NOTE, "The Sobel test is reported for comparison only; rely on the bootstrap interval."],
        evidence=[EvidenceCandidate(
            key=f"mediation:{x}:{m}:{y}", title=f"Indirect association via {lm}", statement=statement, n=n,
            effect_size=std_indirect, effect_label="standardized indirect effect", ci_low=float(ci_low),
            ci_high=float(ci_high), p_value=None,
            strength=("strong" if significant and n >= 200 else "moderate" if significant else "insufficient"),
            value={"indirect": indirect, "a": a, "b": b, "c_prime": c_prime, "c": c_total, "pattern": pattern},
        )],
        charts=[{"type": "path_diagram", "title": "Mediation paths", "x": lx, "m": lm, "y": ly,
                 "paths": {"a": a, "b": b, "c_prime": c_prime, "c": c_total},
                 "p": {"a": p_a, "b": p_b, "c_prime": p_cp, "c": p_c}}],
    )


def moderation(df: pd.DataFrame, x: str, w: str, y: str, covariates: list[str] | None = None,
               center: bool = True, labels: dict[str, str] | None = None) -> AnalysisResult:
    covariates = covariates or []
    labels = labels or {}
    if len({x, w, y}) < 3:
        raise AnalysisError("X, W and Y must be three different variables.")
    data = _frame(df, [x, w, y, *covariates])
    n = len(data)
    if n < 30:
        raise AnalysisError("Moderation needs at least 30 complete cases.")
    w_binary = data[w].nunique() == 2
    Xv = data[x].to_numpy()
    Wv = data[w].to_numpy()
    x_mean = Xv.mean() if center else 0.0
    w_mean = Wv.mean() if (center and not w_binary) else 0.0
    Xc, Wc = Xv - x_mean, Wv - w_mean
    C = data[covariates].to_numpy() if covariates else np.empty((n, 0))
    Y = data[y].to_numpy()
    full = _ols(Y, np.column_stack([Xc, Wc, Xc * Wc, C]))
    reduced = _ols(Y, np.column_stack([Xc, Wc, C]))
    b1, b2, b3 = full.params[1], full.params[2], full.params[3]
    cov = full.cov_params()
    v11, v33, v13 = cov[1, 1], cov[3, 3], cov[1, 3]
    delta_r2 = float(full.rsquared - reduced.rsquared)
    f_change = delta_r2 / ((1 - full.rsquared) / full.df_resid)
    p_change = float(1 - stats.f.cdf(f_change, 1, full.df_resid))
    t_crit = stats.t.ppf(0.975, full.df_resid)

    if w_binary:
        levels = sorted(np.unique(Wv))
        probe = [(float(v), f"{labels.get(w, w)} = {v:g}") for v in levels]
    else:
        sd = Wv.std(ddof=1)
        probe = [(Wv.mean() - sd, "-1 SD"), (Wv.mean(), "Mean"), (Wv.mean() + sd, "+1 SD")]
    slopes = []
    for w_raw, label in probe:
        wv = w_raw - w_mean
        slope = b1 + b3 * wv
        se = math.sqrt(max(v11 + wv**2 * v33 + 2 * wv * v13, 0.0))
        t = slope / se if se > 0 else float("nan")
        p = float(2 * (1 - stats.t.cdf(abs(t), full.df_resid)))
        slopes.append({"w": float(w_raw), "label": label, "slope": float(slope), "se": se, "t": t, "p": p,
                       "ci_low": float(slope - t_crit * se), "ci_high": float(slope + t_crit * se)})

    jn = []
    if not w_binary:
        qa = b3**2 - t_crit**2 * v33
        qb = 2 * b1 * b3 - 2 * t_crit**2 * v13
        qc = b1**2 - t_crit**2 * v11
        disc = qb**2 - 4 * qa * qc
        if qa != 0 and disc >= 0:
            for root in ((-qb - math.sqrt(disc)) / (2 * qa), (-qb + math.sqrt(disc)) / (2 * qa)):
                raw = root + w_mean
                if Wv.min() <= raw <= Wv.max():
                    jn.append(float(raw))

    lx, lw, ly = labels.get(x, x), labels.get(w, w), labels.get(y, y)
    p_int = float(full.pvalues[3])
    statement = (
        f"The association of {lx} with {ly} {'depends' if p_int < 0.05 else 'does not significantly depend'} on {lw} "
        f"(interaction b = {fmt_num(b3, 3)}, {fmt_p(p_int)}, delta R² = {fmt_num(delta_r2, 3)}, n = {n})."
    )
    x_grid = np.linspace(Xv.min(), Xv.max(), 12)
    lines = []
    for w_raw, label in probe:
        wv = w_raw - w_mean
        pred = full.params[0] + b1 * (x_grid - x_mean) + b2 * wv + b3 * (x_grid - x_mean) * wv
        lines.append({"label": label, "points": [{"x": float(a), "y": float(b)} for a, b in zip(x_grid, pred, strict=True)]})
    checks = [
        Check("Mean centering", OK if center else WARNING,
              "X and continuous W were mean-centered; lower-order terms are effects at the mean." if center
              else "Uncentered: lower-order coefficients are effects where the other variable equals zero."),
        Check("Reliability of X and W", NOT_APPLICABLE, "Measurement error in X or W weakens interaction tests."),
        Check("Sample size for interactions", OK if n >= 200 else WARNING,
              f"n = {n}; interaction effects typically need larger samples to detect."),
    ]
    return AnalysisResult(
        method="moderation",
        title=f"Moderation (PROCESS Model 1): {lw} moderating {lx} -> {ly}",
        n=n,
        result={"x": x, "w": w, "y": y, "covariates": covariates, "centered": center,
                "coefficients": [
                    {"term": "Intercept", "b": float(full.params[0]), "se": float(full.bse[0]), "p": float(full.pvalues[0])},
                    {"term": lx, "b": float(b1), "se": float(full.bse[1]), "p": float(full.pvalues[1])},
                    {"term": lw, "b": float(b2), "se": float(full.bse[2]), "p": float(full.pvalues[2])},
                    {"term": f"{lx} x {lw}", "b": float(b3), "se": float(full.bse[3]), "p": p_int},
                ],
                "r2": float(full.rsquared), "delta_r2": delta_r2, "f_change": float(f_change), "p_change": p_change,
                "simple_slopes": slopes, "johnson_neyman": jn},
        assumptions=checks,
        summary=statement,
        limitations=[ASSOCIATION_NOTE],
        evidence=[EvidenceCandidate(
            key=f"moderation:{x}:{w}:{y}", title=f"{lw} moderating {lx} and {ly}", statement=statement, n=n,
            effect_size=delta_r2, effect_label="delta R²", p_value=p_int,
            strength=("moderate" if p_int < 0.05 else "insufficient"),
            value={"interaction": float(b3), "simple_slopes": slopes},
        )],
        charts=[{"type": "line", "title": f"Simple slopes of {lx} on {ly}", "x_label": lx, "y_label": ly, "series": lines}],
    )
