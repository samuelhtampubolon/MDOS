"""Market model schema. Every number is an explicit, editable assumption with a source and confidence."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Source = Literal["evidence", "benchmark", "expert_judgment", "guess"]
Confidence = Literal["low", "medium", "high"]


class Segment(BaseModel):
    key: str
    name: str
    share: float = Field(ge=0, le=1)
    price_elasticity: float = -1.2
    cross_price_elasticity: float = Field(default=0.4, ge=0)
    conversion_multiplier: float = Field(default=1.0, ge=0)
    wtp_multiplier: float = Field(default=1.0, gt=0)
    repeat_rate: float = Field(default=0.05, ge=0, lt=1)
    needs: list[str] = Field(default_factory=list)


class Channel(BaseModel):
    key: str
    name: str
    budget: float = Field(ge=0)
    cpm: float = Field(ge=0, description="Cost per 1,000 impressions")
    audience_size: float = Field(gt=0, description="People reachable in the period")
    engagement_rate: float = Field(ge=0, le=1)
    lead_rate: float = Field(ge=0, le=1)
    conversion_rate: float = Field(ge=0, le=1, description="Lead-to-customer rate at the reference price")
    organic_impressions: float = Field(default=0, ge=0)
    commission_rate: float = Field(default=0, ge=0, lt=1, description="Share of price paid per sale (for example an OTA)")
    affinity: dict[str, float] = Field(default_factory=dict, description="Relative audience weight per segment key")


class Competitor(BaseModel):
    key: str
    name: str
    price: float = Field(ge=0)
    base_price: float | None = Field(default=None, ge=0)
    attributes: dict[str, float] = Field(default_factory=dict)


class Offer(BaseModel):
    name: str
    price: float = Field(gt=0)
    reference_price: float = Field(gt=0, description="Price at which funnel conversion rates were calibrated")
    unit_cost: float = Field(ge=0)
    fixed_costs: float = Field(ge=0)
    capacity: float | None = Field(default=None, gt=0, description="Maximum customers per period, if limited")
    attributes: dict[str, float] = Field(default_factory=dict)


class PricePoint(BaseModel):
    price: float = Field(gt=0)
    share: float = Field(ge=0, le=1)


class PriceResponse(BaseModel):
    mode: Literal["elasticity", "curve"] = "elasticity"
    points: list[PricePoint] = Field(default_factory=list)
    evidence_id: str | None = None

    @model_validator(mode="after")
    def _check_curve(self) -> PriceResponse:
        if self.mode == "curve" and len(self.points) < 2:
            raise ValueError("A price-response curve needs at least two points.")
        return self


class Assumption(BaseModel):
    key: str
    label: str
    value: float | str | None = None
    unit: str = ""
    source: Source = "guess"
    evidence_id: str | None = None
    confidence: Confidence = "low"
    note: str = ""


class MarketModel(BaseModel):
    currency: str = "IDR"
    period: str = "month"
    market_name: str
    market_size: float = Field(gt=0)
    segments: list[Segment] = Field(min_length=1)
    channels: list[Channel] = Field(min_length=1)
    competitors: list[Competitor] = Field(default_factory=list)
    offer: Offer
    price_response: PriceResponse = Field(default_factory=PriceResponse)
    word_of_mouth_rate: float = Field(default=0.0, ge=0, lt=1)
    discount_rate: float = Field(default=0.01, ge=0, lt=1)
    positioning_axes: list[str] = Field(default_factory=lambda: ["Price", "Authenticity"])
    assumptions: list[Assumption] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_shares(self) -> MarketModel:
        total = sum(s.share for s in self.segments)
        if abs(total - 1) > 0.02:
            raise ValueError(f"Segment shares must add up to 100% (currently {total:.0%}).")
        keys = [s.key for s in self.segments] + [c.key for c in self.channels]
        if len(keys) != len(set(keys)):
            raise ValueError("Segment and channel keys must be unique.")
        return self
