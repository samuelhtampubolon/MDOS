"""Registry of analysis methods: parameter schemas, labels and runners.

The API validates parameters against these schemas before running an analysis, and the agents use the
same registry, so both paths produce identical, reproducible results.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field, ValidationError

from . import (
    correlation,
    crosstab,
    descriptive,
    pricing,
    process,
    regression,
    reliability,
    segmentation,
    sentiment,
    text,
)
from .common import AnalysisError, AnalysisResult


class DescriptiveParams(BaseModel):
    columns: list[str] = Field(min_length=1, max_length=100)


class CrosstabParams(BaseModel):
    row: str
    col: str


class CorrelationParams(BaseModel):
    columns: list[str] = Field(min_length=2, max_length=40)
    method: Literal["pearson", "spearman"] = "pearson"


class OLSParams(BaseModel):
    dv: str
    predictors: list[str] = Field(min_length=1, max_length=30)
    robust: Literal["auto", "none", "HC3"] = "auto"
    categorical: list[str] = Field(default_factory=list)


class LogisticParams(BaseModel):
    dv: str
    predictors: list[str] = Field(min_length=1, max_length=30)
    positive: str | None = None
    categorical: list[str] = Field(default_factory=list)


class ReliabilityParams(BaseModel):
    items: list[str] = Field(min_length=2, max_length=50)
    scale_name: str = ""


class MediationParams(BaseModel):
    x: str
    m: str
    y: str
    covariates: list[str] = Field(default_factory=list)
    n_boot: int = Field(default=5000, ge=1000, le=20000)
    seed: int = 20260928


class ModerationParams(BaseModel):
    x: str
    w: str
    y: str
    covariates: list[str] = Field(default_factory=list)
    center: bool = True


class VanWestendorpParams(BaseModel):
    too_cheap: str
    cheap: str
    expensive: str
    too_expensive: str
    target_price: float | None = None


class GaborGrangerParams(BaseModel):
    price_columns: dict[str, str] = Field(min_length=3)
    threshold: float | None = None
    target_price: float | None = None


class WTPParams(BaseModel):
    column: str
    price: float
    group: str | None = None
    positive: str | None = None


class SegmentationParams(BaseModel):
    variables: list[str] = Field(min_length=2, max_length=30)
    objective: str = ""
    rationale: str = ""
    k: int | None = Field(default=None, ge=2, le=10)
    profile_columns: list[str] = Field(default_factory=list)
    text_column: str | None = None
    seed: int = 42


class TextParams(BaseModel):
    text_column: str
    n_topics: int = Field(default=5, ge=2, le=12)
    seed: int = 42


class SentimentParams(BaseModel):
    text_column: str
    group: str | None = None


@dataclass
class Method:
    key: str
    label: str
    category: str
    params: type[BaseModel]
    runner: Callable[..., AnalysisResult]
    description: str


def _run_descriptive(df, p: DescriptiveParams, ctx):
    return descriptive.describe(df, p.columns, ctx["types"], ctx["labels"])


def _run_crosstab(df, p: CrosstabParams, ctx):
    return crosstab.crosstab(df, p.row, p.col, ctx["labels"])


def _run_correlation(df, p: CorrelationParams, ctx):
    return correlation.correlation(df, p.columns, p.method, ctx["labels"])


def _run_ols(df, p: OLSParams, ctx):
    return regression.ols(df, p.dv, p.predictors, robust=p.robust, labels=ctx["labels"], force_categorical=p.categorical)


def _run_logistic(df, p: LogisticParams, ctx):
    return regression.logistic(df, p.dv, p.predictors, positive=p.positive, labels=ctx["labels"],
                               force_categorical=p.categorical)


def _run_reliability(df, p: ReliabilityParams, ctx):
    return reliability.reliability(df, p.items, p.scale_name, ctx["labels"])


def _run_mediation(df, p: MediationParams, ctx):
    return process.mediation(df, p.x, p.m, p.y, p.covariates, n_boot=p.n_boot, seed=p.seed, labels=ctx["labels"])


def _run_moderation(df, p: ModerationParams, ctx):
    return process.moderation(df, p.x, p.w, p.y, p.covariates, center=p.center, labels=ctx["labels"])


def _run_vw(df, p: VanWestendorpParams, ctx):
    return pricing.van_westendorp(df, p.too_cheap, p.cheap, p.expensive, p.too_expensive, p.target_price, ctx["currency"])


def _run_gg(df, p: GaborGrangerParams, ctx):
    return pricing.gabor_granger(df, p.price_columns, p.threshold, p.target_price, ctx["currency"])


def _run_wtp(df, p: WTPParams, ctx):
    return pricing.wtp_at_price(df, p.column, p.price, p.group, p.positive, ctx["currency"])


def _run_segmentation(df, p: SegmentationParams, ctx):
    return segmentation.segment(df, p.variables, p.objective, p.rationale, p.k, p.profile_columns, p.text_column,
                                p.seed, ctx["labels"])


def _run_text(df, p: TextParams, ctx):
    return text.text_themes(df, p.text_column, p.n_topics, p.seed, ctx["labels"])


def _run_sentiment(df, p: SentimentParams, ctx):
    return sentiment.sentiment(df, p.text_column, p.group, ctx["labels"])


METHODS: dict[str, Method] = {
    m.key: m
    for m in [
        Method("descriptive", "Descriptive statistics", "Describe", DescriptiveParams, _run_descriptive,
               "Means, spreads, distributions and frequencies with confidence intervals."),
        Method("crosstab", "Cross-tab and chi-square", "Compare groups", CrosstabParams, _run_crosstab,
               "Association between two categorical variables, with Cramér's V and cell residuals."),
        Method("correlation", "Correlation matrix", "Relationships", CorrelationParams, _run_correlation,
               "Pearson or Spearman correlations with Holm-adjusted p-values."),
        Method("regression_ols", "Linear regression (OLS)", "Relationships", OLSParams, _run_ols,
               "Drivers of a continuous outcome with full assumption checks and robust errors when needed."),
        Method("regression_logistic", "Logistic regression", "Relationships", LogisticParams, _run_logistic,
               "Drivers of a yes/no outcome, reported as odds ratios."),
        Method("reliability", "Reliability (Cronbach's alpha)", "Measurement", ReliabilityParams, _run_reliability,
               "Internal consistency of a multi-item scale with item diagnostics."),
        Method("mediation", "Mediation (PROCESS Model 4)", "Relationships", MediationParams, _run_mediation,
               "Indirect association X to M to Y with a bootstrap confidence interval."),
        Method("moderation", "Moderation (PROCESS Model 1)", "Relationships", ModerationParams, _run_moderation,
               "Whether the X to Y association depends on W, with simple slopes and Johnson-Neyman points."),
        Method("van_westendorp", "Van Westendorp price sensitivity", "Pricing", VanWestendorpParams, _run_vw,
               "Acceptable price range and optimal price point from four price-perception questions."),
        Method("gabor_granger", "Gabor-Granger demand curve", "Pricing", GaborGrangerParams, _run_gg,
               "Purchase intent at several prices, revenue index and elasticities."),
        Method("wtp", "Willingness to pay at a price", "Pricing", WTPParams, _run_wtp,
               "Share willing to pay a specific price, overall and by group."),
        Method("segmentation", "Segmentation (k-means) and personas", "Segments", SegmentationParams, _run_segmentation,
               "Data-driven segments with stability checks, profiles and personas. Requires an objective."),
        Method("text_themes", "Text themes and keywords", "Text", TextParams, _run_text,
               "Keywords, bigrams and NMF themes for English and Indonesian text."),
        Method("sentiment", "Sentiment analysis", "Text", SentimentParams, _run_sentiment,
               "Explainable bilingual lexicon sentiment, overall and by group."),
    ]
}


def catalog() -> list[dict[str, Any]]:
    return [{"key": m.key, "label": m.label, "category": m.category, "description": m.description,
             "params_schema": m.params.model_json_schema()} for m in METHODS.values()]


def run(method: str, df: pd.DataFrame, params: dict[str, Any], *, types: dict[str, str] | None = None,
        labels: dict[str, str] | None = None, currency: str = "IDR") -> tuple[BaseModel, AnalysisResult]:
    if method not in METHODS:
        raise AnalysisError(f"Unknown analysis method '{method}'.")
    spec = METHODS[method]
    try:
        parsed = spec.params.model_validate(params)
    except ValidationError as exc:
        raise AnalysisError(f"Invalid parameters for {spec.label}: {exc.errors()[0]['msg']} at {exc.errors()[0]['loc']}") from exc
    ctx = {"types": types or {}, "labels": labels or {}, "currency": currency}
    return parsed, spec.runner(df, parsed, ctx)
