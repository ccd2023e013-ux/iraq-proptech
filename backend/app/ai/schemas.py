"""Explainable AI result envelopes.

Every AI response says what kind of result it is, how it was produced, how
confident it is, what it is based on and what it cannot tell you.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ResultKind = Literal["generated", "estimate", "analysis", "extraction", "ranking"]


class AIEnvelope(BaseModel):
    feature: str
    kind: ResultKind
    provider: str
    model: str
    generation_id: uuid.UUID | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    methodology: str
    data_sources: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    disclaimer: str | None = None
    created_at: datetime
    result: dict[str, Any]


# --- requests


class DescriptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Literal["ar", "en"] = "ar"


class ImproveTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=5, max_length=5000)


class SearchParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=2, max_length=300)


class ScoreRequest(BaseModel):
    """Weights per criterion (relative; 0 disables a criterion)."""

    model_config = ConfigDict(extra="forbid")

    weights: dict[
        Literal["value", "size", "completeness", "verification", "amenities", "proximity"],
        float,
    ] = Field(default_factory=dict)
    wanted_amenities: list[str] = Field(default_factory=list, max_length=20)
    wanted_poi_categories: list[str] = Field(default_factory=list, max_length=10)


class ReplyDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Literal["ar", "en"] = "ar"


# --- results (documentation)


class PriceEstimate(BaseModel):
    value: Decimal | None
    low: Decimal | None
    high: Decimal | None
    currency: str
    price_per_m2_median: Decimal | None
    comparable_count: int
    asking_price_position: Literal["below_range", "within_range", "above_range"] | None
