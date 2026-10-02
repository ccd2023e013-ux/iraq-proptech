"""/api/v1/locations and /api/v1/reference — public lookup data."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.geo.models import City, District, Governorate, Neighborhood
from app.geo.spatial import point_lonlat
from app.properties.models import Amenity, PropertyType

router = APIRouter(tags=["locations"])

CACHE = "public, max-age=3600"


class PlaceOut(BaseModel):
    id: uuid.UUID
    name_ar: str
    name_en: str
    slug: str
    code: str | None = None
    parent_id: uuid.UUID | None = None
    centroid: dict[str, float] | None = None
    has_boundary: bool
    geometry_source: str | None


class ReferenceOut(BaseModel):
    code: str
    category: str
    name_ar: str
    name_en: str


def _place(row: Any, parent_id: uuid.UUID | None = None) -> PlaceOut:
    centre = point_lonlat(row.centroid)
    return PlaceOut(
        id=row.id,
        name_ar=row.name_ar,
        name_en=row.name_en,
        slug=row.slug,
        code=getattr(row, "code", None),
        parent_id=parent_id,
        centroid={"lon": centre[0], "lat": centre[1]} if centre else None,
        has_boundary=row.boundary is not None,
        geometry_source=row.geometry_source,
    )


@router.get("/locations/governorates", response_model=list[PlaceOut])
def governorates(response: Response, db: Session = Depends(get_db)) -> list[PlaceOut]:
    response.headers["Cache-Control"] = CACHE
    rows = db.execute(
        select(Governorate).where(Governorate.is_active.is_(True)).order_by(Governorate.name_ar)
    ).scalars()
    return [_place(r) for r in rows]


@router.get("/locations/cities", response_model=list[PlaceOut])
def cities(
    response: Response, governorate_id: uuid.UUID | None = None, db: Session = Depends(get_db)
) -> list[PlaceOut]:
    response.headers["Cache-Control"] = CACHE
    stmt = select(City).where(City.is_active.is_(True))
    if governorate_id:
        stmt = stmt.where(City.governorate_id == governorate_id)
    return [_place(r, r.governorate_id) for r in db.execute(stmt.order_by(City.name_ar)).scalars()]


@router.get("/locations/districts", response_model=list[PlaceOut])
def districts(
    response: Response, city_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[PlaceOut]:
    response.headers["Cache-Control"] = CACHE
    rows = db.execute(
        select(District)
        .where(District.city_id == city_id, District.is_active.is_(True))
        .order_by(District.name_ar)
    ).scalars()
    return [_place(r, r.city_id) for r in rows]


@router.get("/locations/neighborhoods", response_model=list[PlaceOut])
def neighborhoods(
    response: Response, district_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[PlaceOut]:
    response.headers["Cache-Control"] = CACHE
    rows = db.execute(
        select(Neighborhood)
        .where(Neighborhood.district_id == district_id, Neighborhood.is_active.is_(True))
        .order_by(Neighborhood.name_ar)
    ).scalars()
    return [_place(r, r.district_id) for r in rows]


@router.get("/reference/property-types", response_model=list[ReferenceOut])
def property_types(response: Response, db: Session = Depends(get_db)) -> list[ReferenceOut]:
    response.headers["Cache-Control"] = CACHE
    rows = db.execute(
        select(PropertyType)
        .where(PropertyType.is_active.is_(True))
        .order_by(PropertyType.sort_order)
    ).scalars()
    return [
        ReferenceOut(code=r.code, category=r.category, name_ar=r.name_ar, name_en=r.name_en)
        for r in rows
    ]


@router.get("/reference/amenities", response_model=list[ReferenceOut])
def amenities(response: Response, db: Session = Depends(get_db)) -> list[ReferenceOut]:
    response.headers["Cache-Control"] = CACHE
    rows = db.execute(
        select(Amenity).where(Amenity.is_active.is_(True)).order_by(Amenity.sort_order)
    ).scalars()
    return [
        ReferenceOut(code=r.code, category=r.category, name_ar=r.name_ar, name_en=r.name_en)
        for r in rows
    ]
