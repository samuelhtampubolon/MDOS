"""Stateless helpers: construct library, analysis catalog, calculators, question parsing."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..analytics import power, registry
from ..analytics.common import AnalysisError
from ..deps import get_current_user
from ..errors import ValidationFailed
from ..research import constructs
from ..research.design import parse_question

router = APIRouter(prefix="/tools", tags=["tools"], dependencies=[Depends(get_current_user)])


class SampleSizeIn(BaseModel):
    kind: Literal["proportion", "mean", "ab_test", "margin_of_error"] = "proportion"
    p: float = 0.5
    margin: float = 0.05
    confidence: float = 0.95
    population: int | None = None
    sd: float | None = None
    n: int | None = None
    baseline: float | None = None
    mde_relative: float | None = None
    alpha: float = 0.05
    power: float = 0.8


class ParseIn(BaseModel):
    text: str = Field(min_length=5, max_length=4000)
    currency: str = "IDR"


@router.get("/constructs")
def construct_library(q: str = "", tags: str = "") -> list[dict]:
    return constructs.search(q, [t for t in tags.split(",") if t])


@router.get("/analysis-methods")
def analysis_methods() -> list[dict]:
    return registry.catalog()


@router.post("/sample-size")
def sample_size(body: SampleSizeIn) -> dict:
    try:
        if body.kind == "proportion":
            return power.sample_size_proportion(body.p, body.margin, body.confidence, body.population)
        if body.kind == "mean":
            if body.sd is None:
                raise ValidationFailed("sd is required for a mean.")
            return power.sample_size_mean(body.sd, body.margin, body.confidence, body.population)
        if body.kind == "margin_of_error":
            if body.n is None:
                raise ValidationFailed("n is required.")
            return {"n": body.n, "margin_of_error": power.margin_of_error(body.n, body.p, body.confidence, body.population)}
        if body.baseline is None or body.mde_relative is None:
            raise ValidationFailed("baseline and mde_relative are required for an A/B test.")
        return power.ab_sample_size(body.baseline, body.mde_relative, body.alpha, body.power)
    except AnalysisError as exc:
        raise ValidationFailed(str(exc)) from exc


@router.post("/parse-question")
def parse(body: ParseIn) -> dict:
    return parse_question(body.text, body.currency).__dict__
