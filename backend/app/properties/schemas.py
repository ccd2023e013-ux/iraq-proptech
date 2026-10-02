from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.properties.enums import (
    Condition,
    Currency,
    DocumentType,
    Furnishing,
    LocationPrivacy,
    ModerationReason,
    OwnershipDocument,
    Purpose,
    RentPeriod,
    VerificationKind,
    VerificationResult,
)

# Iraq's bounding box (WGS84), with a small margin.
IRAQ_LON = (38.7, 48.9)
IRAQ_LAT = (29.0, 37.5)
RENT_LIKE = {Purpose.RENT, Purpose.LEASE}


class GeoPoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)

    @model_validator(mode="after")
    def _inside_iraq(self) -> GeoPoint:
        if not (IRAQ_LON[0] <= self.lon <= IRAQ_LON[1] and IRAQ_LAT[0] <= self.lat <= IRAQ_LAT[1]):
            raise ValueError("Coordinates must be inside Iraq")
        return self


TWO_PLACES = Decimal("0.01")


def _quantize(value: Decimal | None) -> Decimal | None:
    """Money and areas always carry exactly two decimals (as stored)."""
    return None if value is None else value.quantize(TWO_PLACES)


class LatLon(BaseModel):
    lat: float
    lon: float


class _PropertyFields(BaseModel):
    title_ar: str = Field(min_length=5, max_length=200)
    title_en: str | None = Field(default=None, max_length=200)
    description_ar: str | None = Field(default=None, max_length=8000)
    description_en: str | None = Field(default=None, max_length=8000)

    property_type_code: str = Field(min_length=2, max_length=32)
    purpose: Purpose
    rent_period: RentPeriod | None = None

    price_amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    currency: Currency = Currency.IQD
    price_on_request: bool = False
    negotiable: bool = False

    area_m2: Decimal | None = Field(default=None, gt=0, le=10_000_000, decimal_places=2)
    land_area_m2: Decimal | None = Field(default=None, gt=0, le=100_000_000, decimal_places=2)
    bedrooms: int | None = Field(default=None, ge=0, le=100)
    bathrooms: int | None = Field(default=None, ge=0, le=100)
    floors: int | None = Field(default=None, ge=0, le=200)
    floor_number: int | None = Field(default=None, ge=-5, le=200)
    year_built: int | None = Field(default=None, ge=1800, le=2100)
    condition: Condition | None = None
    furnishing: Furnishing | None = None
    ownership_document: OwnershipDocument = OwnershipDocument.UNKNOWN
    amenities: list[str] = Field(default_factory=list, max_length=60)

    governorate_id: uuid.UUID
    city_id: uuid.UUID
    district_id: uuid.UUID | None = None
    neighborhood_id: uuid.UUID | None = None
    street: str | None = Field(default=None, max_length=200)
    address_text: str | None = Field(default=None, max_length=300)
    location: GeoPoint | None = None
    location_privacy: LocationPrivacy = LocationPrivacy.APPROXIMATE

    show_phone: bool = False
    allow_whatsapp: bool = False
    virtual_tour_url: HttpUrl | None = None
    agent_id: uuid.UUID | None = None

    @field_validator("virtual_tour_url")
    @classmethod
    def _https(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None and value.scheme != "https":
            raise ValueError("Virtual tour links must use https")
        return value

    @field_validator("amenities")
    @classmethod
    def _dedupe(cls, value: list[str]) -> list[str]:
        return sorted(set(value))

    _decimals = field_validator("price_amount", "area_m2", "land_area_m2")(_quantize)


def check_price_rules(
    *,
    purpose: str | None,
    rent_period: str | None,
    price_amount: Decimal | None,
    price_on_request: bool | None,
) -> None:
    if price_on_request and price_amount is not None:
        raise ValueError("Set either a price or 'price on request', not both")
    if not price_on_request and price_amount is None:
        raise ValueError("A price is required unless 'price on request' is selected")
    if purpose in RENT_LIKE and rent_period is None:
        raise ValueError("Rent listings need a rent period")
    if purpose not in RENT_LIKE and rent_period is not None:
        raise ValueError("Rent period only applies to rent/lease listings")


class PropertyCreate(_PropertyFields):
    @model_validator(mode="after")
    def _rules(self) -> PropertyCreate:
        check_price_rules(
            purpose=self.purpose,
            rent_period=self.rent_period,
            price_amount=self.price_amount,
            price_on_request=self.price_on_request,
        )
        return self


class PropertyUpdate(BaseModel):
    """Partial update: only provided fields change. Cross-field rules are
    re-checked against the merged result in the service."""

    title_ar: str | None = Field(default=None, min_length=5, max_length=200)
    title_en: str | None = Field(default=None, max_length=200)
    description_ar: str | None = Field(default=None, max_length=8000)
    description_en: str | None = Field(default=None, max_length=8000)
    property_type_code: str | None = Field(default=None, min_length=2, max_length=32)
    purpose: Purpose | None = None
    rent_period: RentPeriod | None = None
    price_amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    currency: Currency | None = None
    price_on_request: bool | None = None
    negotiable: bool | None = None
    area_m2: Decimal | None = Field(default=None, gt=0, le=10_000_000, decimal_places=2)
    land_area_m2: Decimal | None = Field(default=None, gt=0, le=100_000_000, decimal_places=2)
    bedrooms: int | None = Field(default=None, ge=0, le=100)
    bathrooms: int | None = Field(default=None, ge=0, le=100)
    floors: int | None = Field(default=None, ge=0, le=200)
    floor_number: int | None = Field(default=None, ge=-5, le=200)
    year_built: int | None = Field(default=None, ge=1800, le=2100)
    condition: Condition | None = None
    furnishing: Furnishing | None = None
    ownership_document: OwnershipDocument | None = None
    amenities: list[str] | None = Field(default=None, max_length=60)
    governorate_id: uuid.UUID | None = None
    city_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None
    neighborhood_id: uuid.UUID | None = None
    street: str | None = Field(default=None, max_length=200)
    address_text: str | None = Field(default=None, max_length=300)
    location: GeoPoint | None = None
    location_privacy: LocationPrivacy | None = None
    show_phone: bool | None = None
    allow_whatsapp: bool | None = None
    virtual_tour_url: HttpUrl | None = None
    agent_id: uuid.UUID | None = None

    _decimals = field_validator("price_amount", "area_m2", "land_area_m2")(_quantize)


class StatusChangeIn(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class ModerationIn(BaseModel):
    decision: str = Field(pattern="^(APPROVE|REJECT|SUSPEND|REINSTATE)$")
    reason: str | None = Field(default=None, max_length=1000)
    reason_code: ModerationReason | None = None


class VerificationIn(BaseModel):
    kind: VerificationKind
    result: VerificationResult
    note: str | None = Field(default=None, max_length=2000)
    document_id: uuid.UUID | None = None


class VerificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    result: str
    note: str | None
    created_at: datetime


class MediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    content_type: str
    width: int | None
    height: int | None
    sort_order: int
    caption: str | None
    url: str = ""
    thumbnail_url: str | None = None


class MediaOrderIn(BaseModel):
    media_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doc_type: DocumentType
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime


class PlaceRef(BaseModel):
    id: uuid.UUID
    name_ar: str
    name_en: str


class ListerOut(BaseModel):
    """Public identity of whoever offers the listing (no private contact data)."""

    kind: str  # "agency" | "agent" | "owner"
    name: str
    agency_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    phone: str | None = None  # only when the lister chose to show it
    whatsapp: str | None = None
    agency_verified: bool = False


class PriceHistoryOut(BaseModel):
    price_amount: Decimal | None
    currency: str
    price_on_request: bool
    changed_at: datetime


class StatusHistoryOut(BaseModel):
    from_status: str | None
    to_status: str
    reason: str | None
    changed_at: datetime


class PropertyOut(BaseModel):
    """Public representation. Private fields are filled only for authorized viewers."""

    id: uuid.UUID
    reference_code: str
    title_ar: str
    title_en: str | None
    description_ar: str | None
    description_en: str | None
    property_type_code: str
    purpose: str
    rent_period: str | None
    price_amount: Decimal | None
    currency: str
    price_on_request: bool
    negotiable: bool
    area_m2: Decimal | None
    land_area_m2: Decimal | None
    bedrooms: int | None
    bathrooms: int | None
    floors: int | None
    floor_number: int | None
    year_built: int | None
    condition: str | None
    furnishing: str | None
    ownership_document: str
    amenities: list[str]
    governorate: PlaceRef
    city: PlaceRef
    district: PlaceRef | None
    neighborhood: PlaceRef | None
    street: str | None
    address_text: str | None
    location_privacy: str
    display_location: LatLon | None
    status: str
    published_at: datetime | None
    expires_at: datetime | None
    verified: bool
    verified_at: datetime | None
    is_demo: bool
    created_at: datetime
    updated_at: datetime
    virtual_tour_url: str | None
    media: list[MediaOut]
    lister: ListerOut
    # Private (owner/agent/agency owner/moderators only)
    exact_location: LatLon | None = None
    status_reason: str | None = None
    status_reason_code: str | None = None
    needs_review: bool | None = None
    show_phone: bool | None = None
    allow_whatsapp: bool | None = None
    agent_id: uuid.UUID | None = None
    can_edit: bool = False


class PropertyCard(BaseModel):
    """Compact listing representation for result lists."""

    id: uuid.UUID
    reference_code: str
    title_ar: str
    title_en: str | None
    property_type_code: str
    purpose: str
    rent_period: str | None
    price_amount: Decimal | None
    currency: str
    price_on_request: bool
    area_m2: Decimal | None
    bedrooms: int | None
    bathrooms: int | None
    city: PlaceRef
    district: PlaceRef | None
    neighborhood: PlaceRef | None
    display_location: LatLon | None
    status: str
    verified: bool
    is_demo: bool
    published_at: datetime | None
    created_at: datetime
    cover_url: str | None
    agency_name: str | None = None
