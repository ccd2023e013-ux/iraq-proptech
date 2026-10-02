"""Points of interest and "nearby" queries.

POIs are data with a mandatory ``source`` (licence/attribution). Nothing is
scraped; demo POIs are flagged ``is_demo`` and named as demo. Distances are
computed from a listing's *public* display point, so for approximate
locations they are approximate too (``approximate=true`` in responses).
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from geoalchemy2 import Geography
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    cast,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.audit import service as audit
from app.auth.deps import Principal, get_optional_principal, require_permission
from app.core.errors import AppError, NotFoundError
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.session import get_db
from app.geo.manage import IRAQ_LAT, IRAQ_LON
from app.geo.models import point
from app.geo.spatial import make_point, point_lonlat
from app.policies import can_view_private_property
from app.properties.models import Property
from app.properties.presenter import to_cards
from app.properties.schemas import PropertyCard
from app.properties.service import get_property_or_404
from app.rbac.catalog import Permission
from app.search.schemas import SearchFilters
from app.search.service import build_query


class PoiCategory(StrEnum):
    SCHOOL = "SCHOOL"
    UNIVERSITY = "UNIVERSITY"
    HOSPITAL = "HOSPITAL"
    CLINIC = "CLINIC"
    PHARMACY = "PHARMACY"
    MOSQUE = "MOSQUE"
    CHURCH = "CHURCH"
    MARKET = "MARKET"
    MALL = "MALL"
    PARK = "PARK"
    GOVERNMENT = "GOVERNMENT"
    BANK = "BANK"
    FUEL = "FUEL"
    TRANSPORT = "TRANSPORT"
    RESTAURANT = "RESTAURANT"
    OTHER = "OTHER"


class PointOfInterest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "points_of_interest"
    __table_args__ = (
        CheckConstraint(
            "category IN (" + ",".join(f"'{c.value}'" for c in PoiCategory) + ")",
            name="category_valid",
        ),
        Index("ix_points_of_interest_location", "location", postgresql_using="gist"),
    )

    category: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[Any] = mapped_column(point(), nullable=False)
    city_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cities.id", ondelete="SET NULL"), index=True
    )
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(120))
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


# --------------------------------------------------------------------------- schemas


class PoiIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: PoiCategory
    name_ar: str = Field(min_length=2, max_length=200)
    name_en: str | None = Field(default=None, max_length=200)
    lat: float
    lon: float
    city_id: uuid.UUID | None = None
    source: str = Field(min_length=3, max_length=200)
    external_ref: str | None = Field(default=None, max_length=120)

    @field_validator("lon")
    @classmethod
    def _lon(cls, v: float) -> float:
        if not IRAQ_LON[0] <= v <= IRAQ_LON[1]:
            raise ValueError("longitude outside Iraq")
        return v

    @field_validator("lat")
    @classmethod
    def _lat(cls, v: float) -> float:
        if not IRAQ_LAT[0] <= v <= IRAQ_LAT[1]:
            raise ValueError("latitude outside Iraq")
        return v


class PoiImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PoiIn] = Field(min_length=1, max_length=1000)


class PoiOut(BaseModel):
    id: uuid.UUID
    category: str
    name_ar: str
    name_en: str | None
    lat: float
    lon: float
    source: str
    is_demo: bool
    distance_m: float | None = None


class NearbyOut(BaseModel):
    property_id: uuid.UUID
    radius_m: int
    approximate: bool = Field(description="True when the listing shows an approximate location")
    available: bool = Field(description="False when the listing has no public location")
    by_category: dict[str, list[PoiOut]]
    total: int


class NearbyPropertiesOut(BaseModel):
    property_id: uuid.UUID
    radius_m: int
    approximate: bool
    items: list[PropertyCard]
    distances_m: dict[str, float]


def _poi_out(p: PointOfInterest, distance: float | None = None) -> PoiOut:
    lonlat = point_lonlat(p.location)
    assert lonlat is not None  # noqa: S101 - NOT NULL column
    return PoiOut(
        id=p.id,
        category=p.category,
        name_ar=p.name_ar,
        name_en=p.name_en,
        lat=lonlat[1],
        lon=lonlat[0],
        source=p.source,
        is_demo=p.is_demo,
        distance_m=None if distance is None else round(float(distance), 1),
    )


def _geog(col: Any) -> Any:
    return cast(col, Geography(geometry_type="POINT", srid=4326))


router = APIRouter(tags=["pois"])


def _visible_property(db: Session, principal: Principal | None, property_id: uuid.UUID) -> Property:
    prop = get_property_or_404(db, property_id)
    if prop.is_public or can_view_private_property(
        db, principal, lister_id=prop.lister_id, agency_id=prop.agency_id, agent_id=prop.agent_id
    ):
        return prop
    raise NotFoundError("Property not found", code="PROPERTY_NOT_FOUND")


@router.get("/pois", response_model=list[PoiOut])
def list_pois(
    bbox: str = Query(max_length=120, description="west,south,east,north"),
    category: list[PoiCategory] | None = Query(default=None),
    include_demo: bool = True,
    db: Session = Depends(get_db),
) -> list[PoiOut]:
    try:
        west, south, east, north = (float(v) for v in bbox.split(","))
    except ValueError as exc:
        raise AppError("bbox must be 'west,south,east,north'", code="VALIDATION_ERROR") from exc
    if west >= east or south >= north or (east - west) * (north - south) > 4:
        raise AppError("Invalid or too large bbox", code="VALIDATION_ERROR", status_code=422)
    stmt = select(PointOfInterest).where(
        PointOfInterest.is_active.is_(True),
        func.ST_Intersects(
            PointOfInterest.location, func.ST_MakeEnvelope(west, south, east, north, 4326)
        ),
    )
    if category:
        stmt = stmt.where(PointOfInterest.category.in_([c.value for c in category]))
    if not include_demo:
        stmt = stmt.where(PointOfInterest.is_demo.is_(False))
    return [_poi_out(p) for p in db.execute(stmt.limit(2000)).scalars()]


@router.get("/properties/{property_id}/nearby", response_model=NearbyOut)
def nearby_pois(
    property_id: uuid.UUID,
    radius_m: int = Query(1500, ge=100, le=10_000),
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> NearbyOut:
    prop = _visible_property(db, principal, property_id)
    if prop.display_location is None:
        return NearbyOut(
            property_id=prop.id,
            radius_m=radius_m,
            approximate=False,
            available=False,
            by_category={},
            total=0,
        )
    centre = _geog(
        select(Property.display_location).where(Property.id == prop.id).scalar_subquery()
    )
    distance = func.ST_Distance(_geog(PointOfInterest.location), centre)
    rows = db.execute(
        select(PointOfInterest, distance)
        .where(
            PointOfInterest.is_active.is_(True),
            func.ST_DWithin(_geog(PointOfInterest.location), centre, radius_m),
        )
        .order_by(distance)
        .limit(200)
    ).all()
    grouped: dict[str, list[PoiOut]] = {}
    for poi, dist in rows:
        bucket = grouped.setdefault(poi.category, [])
        if len(bucket) < 10:
            bucket.append(_poi_out(poi, dist))
    return NearbyOut(
        property_id=prop.id,
        radius_m=radius_m,
        approximate=prop.location_privacy != "EXACT",
        available=True,
        by_category=grouped,
        total=len(rows),
    )


@router.get("/properties/{property_id}/nearby-properties", response_model=NearbyPropertiesOut)
def nearby_properties(
    property_id: uuid.UUID,
    radius_m: int = Query(2000, ge=100, le=20_000),
    limit: int = Query(8, ge=1, le=30),
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> NearbyPropertiesOut:
    """Other public listings near this one (distance between public points)."""
    prop = _visible_property(db, principal, property_id)
    if prop.display_location is None:
        return NearbyPropertiesOut(
            property_id=prop.id, radius_m=radius_m, approximate=False, items=[], distances_m={}
        )
    centre = _geog(
        select(Property.display_location).where(Property.id == prop.id).scalar_subquery()
    )
    base, _ = build_query(SearchFilters())
    distance = func.ST_Distance(_geog(Property.display_location), centre)
    rows = db.execute(
        base.order_by(None)
        .add_columns(distance)
        .where(
            Property.id != prop.id,
            Property.display_location.is_not(None),
            func.ST_DWithin(_geog(Property.display_location), centre, radius_m),
        )
        .order_by(distance, Property.id)
        .limit(limit)
    ).all()
    props = [r[0] for r in rows]
    return NearbyPropertiesOut(
        property_id=prop.id,
        radius_m=radius_m,
        approximate=prop.location_privacy != "EXACT",
        items=to_cards(db, props),
        distances_m={str(r[0].id): round(float(r[1]), 1) for r in rows},
    )


# --------------------------------------------------------------------------- admin


def _make(body: PoiIn, *, demo: bool = False) -> PointOfInterest:
    return PointOfInterest(
        category=body.category,
        name_ar=body.name_ar.strip(),
        name_en=body.name_en.strip() if body.name_en else None,
        location=make_point(body.lon, body.lat),
        city_id=body.city_id,
        source=body.source.strip(),
        external_ref=body.external_ref,
        is_demo=demo,
        is_active=True,
    )


@router.post("/admin/pois", response_model=PoiOut, status_code=status.HTTP_201_CREATED)
def create_poi(
    body: PoiIn,
    principal: Principal = Depends(require_permission(Permission.LOCATIONS_MANAGE)),
    db: Session = Depends(get_db),
) -> PoiOut:
    poi = _make(body)
    db.add(poi)
    db.flush()
    audit.record(db, "poi.created", actor_id=principal.id, resource_type="poi", resource_id=poi.id)
    db.commit()
    db.refresh(poi)
    return _poi_out(poi)


@router.post("/admin/pois/import", status_code=status.HTTP_201_CREATED)
def import_pois(
    body: PoiImport,
    principal: Principal = Depends(require_permission(Permission.LOCATIONS_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Bulk import (e.g. converted from an openly-licensed dataset). All-or-nothing."""
    db.add_all([_make(item) for item in body.items])
    audit.record(
        db,
        "poi.imported",
        actor_id=principal.id,
        resource_type="poi",
        data={
            "count": len(body.items),
            "sources": ",".join(sorted({i.source for i in body.items}))[:500],
        },
    )
    db.commit()
    return {"imported": len(body.items)}


@router.delete("/admin/pois/{poi_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_poi(
    poi_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.LOCATIONS_MANAGE)),
    db: Session = Depends(get_db),
) -> None:
    poi = db.get(PointOfInterest, poi_id)
    if poi is None:
        raise NotFoundError("POI not found", code="POI_NOT_FOUND")
    db.delete(poi)
    audit.record(db, "poi.deleted", actor_id=principal.id, resource_type="poi", resource_id=poi_id)
    db.commit()
