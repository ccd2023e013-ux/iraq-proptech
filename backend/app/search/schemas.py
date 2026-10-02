"""Structured property search.

``SearchFilters`` is the single, validated search contract. The web UI, the
public API, saved searches and the AI natural-language search all produce
this structure — nothing ever builds SQL from free text.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.properties.enums import Condition, Currency, Furnishing, Purpose, RentPeriod


class SortOrder(StrEnum):
    NEWEST = "newest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    AREA_DESC = "area_desc"
    AREA_ASC = "area_asc"
    RELEVANCE = "relevance"
    DISTANCE = "distance"  # only with a radius search


class BBox(BaseModel):
    """Map viewport: west, south, east, north (WGS84)."""

    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)

    @model_validator(mode="after")
    def _ordered(self) -> BBox:
        if self.west >= self.east or self.south >= self.north:
            raise ValueError("Invalid bounding box")
        if (self.east - self.west) * (self.north - self.south) > 400:
            raise ValueError("Bounding box is too large")
        return self


class SearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(default=None, max_length=200)
    governorate_id: uuid.UUID | None = None
    city_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None
    neighborhood_id: uuid.UUID | None = None
    property_types: list[str] = Field(default_factory=list, max_length=20)
    purpose: Purpose | None = None
    rent_period: RentPeriod | None = None
    currency: Currency | None = None
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, ge=0)
    min_area: Decimal | None = Field(default=None, ge=0)
    max_area: Decimal | None = Field(default=None, ge=0)
    bedrooms_min: int | None = Field(default=None, ge=0, le=50)
    bathrooms_min: int | None = Field(default=None, ge=0, le=50)
    amenities: list[str] = Field(default_factory=list, max_length=30)
    furnishing: Furnishing | None = None
    condition: Condition | None = None
    verified_only: bool = False
    exclude_demo: bool = False
    agency_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    posted_within_days: int | None = Field(default=None, ge=1, le=365)
    # Spatial (Phase 5)
    bbox: BBox | None = None
    near_lat: float | None = Field(default=None, ge=-90, le=90)
    near_lon: float | None = Field(default=None, ge=-180, le=180)
    radius_km: float | None = Field(default=None, gt=0, le=100)
    polygon: list[tuple[float, float]] | None = Field(default=None, min_length=4, max_length=200)
    sort: SortOrder = SortOrder.NEWEST

    @model_validator(mode="after")
    def _consistent(self) -> SearchFilters:
        if (self.min_price is not None or self.max_price is not None) and self.currency is None:
            raise ValueError(
                "Price filters need a currency: prices are never converted between IQD and USD"
            )
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price must not exceed max_price")
        if (
            self.min_area is not None
            and self.max_area is not None
            and self.min_area > self.max_area
        ):
            raise ValueError("min_area must not exceed max_area")
        radius_parts = (self.near_lat, self.near_lon, self.radius_km)
        if any(p is not None for p in radius_parts) and not all(
            p is not None for p in radius_parts
        ):
            raise ValueError("near_lat, near_lon and radius_km must be given together")
        if self.sort == SortOrder.DISTANCE and self.radius_km is None:
            raise ValueError("Distance sort needs a radius search")
        if self.sort == SortOrder.RELEVANCE and not self.q:
            self.sort = SortOrder.NEWEST
        if self.polygon is not None and self.polygon[0] != self.polygon[-1]:
            self.polygon = [*self.polygon, self.polygon[0]]  # close the ring
        self.property_types = sorted(set(self.property_types))
        self.amenities = sorted(set(self.amenities))
        return self

    def is_empty(self) -> bool:
        return self == SearchFilters(sort=self.sort)
