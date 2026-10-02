"""GIS endpoints: boundaries as GeoJSON, point → place resolution, and
administration of districts, neighborhoods and their polygons.

Boundaries are optional data. Where one is missing the API says so
(`has_boundary=false`, centroid only) instead of fabricating a shape, and
every geometry carries its `geometry_source` so approximate or demo shapes
are never presented as official.
"""

from __future__ import annotations

import json
import re
import uuid
from enum import StrEnum
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, literal, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.auth.deps import Principal, require_permission
from app.core.errors import AppError, ConflictError, NotFoundError
from app.db.session import get_db
from app.geo.models import SRID, City, District, Governorate, Neighborhood
from app.geo.spatial import make_point, point_lonlat
from app.rbac.catalog import Permission

router = APIRouter(tags=["locations"])

# Iraq's extent with a small margin (boundaries may touch the borders).
IRAQ_LON = (38.5, 49.0)
IRAQ_LAT = (28.9, 37.6)
MAX_VERTICES = 20_000
NEAREST_CITY_MAX_KM = 40.0
CACHE = "public, max-age=600"


class Level(StrEnum):
    GOVERNORATES = "governorates"
    CITIES = "cities"
    DISTRICTS = "districts"
    NEIGHBORHOODS = "neighborhoods"


MODELS: dict[Level, Any] = {
    Level.GOVERNORATES: Governorate,
    Level.CITIES: City,
    Level.DISTRICTS: District,
    Level.NEIGHBORHOODS: Neighborhood,
}
PARENT: dict[Level, tuple[Level, str] | None] = {
    Level.GOVERNORATES: None,
    Level.CITIES: (Level.GOVERNORATES, "governorate_id"),
    Level.DISTRICTS: (Level.CITIES, "city_id"),
    Level.NEIGHBORHOODS: (Level.DISTRICTS, "district_id"),
}


# --------------------------------------------------------------------------- schemas


def _check_position(position: Any) -> None:
    if not isinstance(position, list | tuple) or len(position) < 2:
        raise ValueError("each position must be [lon, lat]")
    lon, lat = position[0], position[1]
    if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in (lon, lat)):
        raise ValueError("coordinates must be numbers")
    if not (IRAQ_LON[0] <= lon <= IRAQ_LON[1] and IRAQ_LAT[0] <= lat <= IRAQ_LAT[1]):
        raise ValueError("coordinates must be inside Iraq (lon, lat order, WGS84)")


def _check_ring(ring: Any) -> int:
    if not isinstance(ring, list) or len(ring) < 4:
        raise ValueError("a ring needs at least 4 positions")
    for position in ring:
        _check_position(position)
    if list(ring[0][:2]) != list(ring[-1][:2]):
        raise ValueError("rings must be closed (first position == last position)")
    return len(ring)


class PolygonGeometry(BaseModel):
    """A GeoJSON Polygon or MultiPolygon in WGS84 (RFC 7946)."""

    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list[Any]

    @model_validator(mode="after")
    def _validate(self) -> PolygonGeometry:
        polygons = [self.coordinates] if self.type == "Polygon" else self.coordinates
        if not polygons:
            raise ValueError("empty geometry")
        vertices = 0
        for polygon in polygons:
            if not isinstance(polygon, list) or not polygon:
                raise ValueError("a polygon needs at least one ring")
            for ring in polygon:
                vertices += _check_ring(ring)
        if vertices > MAX_VERTICES:
            raise ValueError(f"too many vertices (max {MAX_VERTICES}); simplify the boundary")
        return self


class BoundaryIn(BaseModel):
    geometry: PolygonGeometry
    source: str = Field(min_length=3, max_length=200)


class PlaceCreate(BaseModel):
    parent_id: uuid.UUID
    name_ar: str = Field(min_length=2, max_length=120)
    name_en: str = Field(min_length=2, max_length=120)
    slug: str | None = Field(default=None, max_length=80)
    centroid: dict[str, float] | None = None
    boundary: BoundaryIn | None = None

    @field_validator("slug")
    @classmethod
    def _slug(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
            raise ValueError("slug must be lowercase latin letters, digits and dashes")
        return value

    @field_validator("centroid")
    @classmethod
    def _centroid(cls, value: dict[str, float] | None) -> dict[str, float] | None:
        if value is not None:
            if set(value) != {"lat", "lon"}:
                raise ValueError("centroid must be {lat, lon}")
            _check_position([value["lon"], value["lat"]])
        return value


class PlaceSummary(BaseModel):
    id: uuid.UUID
    name_ar: str
    name_en: str


class ResolveOut(BaseModel):
    governorate: PlaceSummary | None
    city: PlaceSummary | None
    district: PlaceSummary | None
    neighborhood: PlaceSummary | None
    method: Literal["boundary", "nearest_city_centroid", "none"]
    approximate: bool
    distance_km: float | None = None


# --------------------------------------------------------------------------- helpers


def _geometry_sql(geometry: PolygonGeometry) -> Any:
    """Validated GeoJSON → MULTIPOLYGON (repaired with ST_MakeValid), bound as a parameter."""
    raw = func.ST_SetSRID(func.ST_GeomFromGeoJSON(literal(json.dumps(geometry.model_dump()))), SRID)
    return func.ST_Multi(func.ST_CollectionExtract(func.ST_MakeValid(raw), 3))


def _get(db: Session, level: Level, place_id: uuid.UUID) -> Any:
    place = db.get(MODELS[level], place_id)
    if place is None:
        raise NotFoundError("Location not found", code="LOCATION_NOT_FOUND")
    return place


def _summary(place: Any | None) -> PlaceSummary | None:
    if place is None:
        return None
    return PlaceSummary(id=place.id, name_ar=place.name_ar, name_en=place.name_en)


def _slugify(name_en: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name_en.lower()).strip("-")
    return slug[:80] or "place"


def _feature(level: Level, place: Any, geometry: str | None) -> dict[str, Any]:
    centre = point_lonlat(place.centroid)
    geo: dict[str, Any] | None
    if geometry is not None:
        geo = json.loads(geometry)
    elif centre is not None:
        geo = {"type": "Point", "coordinates": [centre[0], centre[1]]}
    else:
        geo = None
    return {
        "type": "Feature",
        "id": str(place.id),
        "geometry": geo,
        "properties": {
            "id": str(place.id),
            "level": level.value,
            "name_ar": place.name_ar,
            "name_en": place.name_en,
            "has_boundary": geometry is not None,
            "geometry_source": place.geometry_source,
            "centroid": {"lon": centre[0], "lat": centre[1]} if centre else None,
        },
    }


# --------------------------------------------------------------------------- public


@router.get("/locations/{level}/{place_id}/geojson")
def place_geojson(
    level: Level, place_id: uuid.UUID, response: Response, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """The place's boundary (or centroid point when no boundary exists) as a GeoJSON Feature."""
    model = MODELS[level]
    row = db.execute(
        select(model, func.ST_AsGeoJSON(model.boundary, 6)).where(model.id == place_id)
    ).first()
    if row is None:
        raise NotFoundError("Location not found", code="LOCATION_NOT_FOUND")
    response.headers["Cache-Control"] = CACHE
    return _feature(level, row[0], row[1])


@router.get("/locations/boundaries")
def boundaries(
    response: Response,
    level: Level,
    parent_id: uuid.UUID | None = None,
    simplify: float = Query(0.0001, ge=0, le=0.01, description="tolerance in degrees"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Boundaries of every place at `level` (optionally under `parent_id`) that has one."""
    model = MODELS[level]
    parent = PARENT[level]
    if parent_id is not None and parent is None:
        raise AppError("Governorates have no parent", code="VALIDATION_ERROR", status_code=422)
    if parent_id is None and level in (Level.DISTRICTS, Level.NEIGHBORHOODS):
        raise AppError(
            "parent_id is required at this level", code="VALIDATION_ERROR", status_code=422
        )
    shape = (
        model.boundary
        if simplify == 0
        else func.ST_SimplifyPreserveTopology(model.boundary, simplify)
    )
    stmt = select(model, func.ST_AsGeoJSON(shape, 6)).where(
        model.boundary.is_not(None), model.is_active.is_(True)
    )
    if parent_id is not None and parent is not None:
        stmt = stmt.where(getattr(model, parent[1]) == parent_id)
    rows = db.execute(stmt.order_by(model.name_ar).limit(2000)).all()
    response.headers["Cache-Control"] = CACHE
    return {"type": "FeatureCollection", "features": [_feature(level, p, g) for p, g in rows]}


@router.get("/locations/resolve", response_model=ResolveOut)
def resolve(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    db: Session = Depends(get_db),
) -> ResolveOut:
    """Which governorate/city/district/neighborhood contains a point.

    Uses boundaries where they exist; otherwise falls back to the nearest city
    centroid (flagged `approximate`). Never guesses beyond that.
    """
    if not (IRAQ_LON[0] <= lon <= IRAQ_LON[1] and IRAQ_LAT[0] <= lat <= IRAQ_LAT[1]):
        raise AppError("Point is outside Iraq", code="OUTSIDE_IRAQ", status_code=422)
    pt = make_point(lon, lat)

    def containing(model: Any) -> Any | None:
        return db.execute(
            select(model)
            .where(model.boundary.is_not(None), func.ST_Covers(model.boundary, pt))
            .order_by(func.ST_Area(model.boundary))
            .limit(1)
        ).scalar_one_or_none()

    neighborhood = containing(Neighborhood)
    district = db.get(District, neighborhood.district_id) if neighborhood else containing(District)
    city = db.get(City, district.city_id) if district else containing(City)
    method: Literal["boundary", "nearest_city_centroid", "none"] = "boundary"
    distance_km: float | None = None
    if city is None:
        geog = func.Geography(func.ST_GeomFromText(f"POINT({lon} {lat})", SRID))
        row = db.execute(
            select(City, func.ST_Distance(func.Geography(City.centroid), geog) / 1000.0)
            .where(City.centroid.is_not(None), City.is_active.is_(True))
            .order_by(func.ST_Distance(func.Geography(City.centroid), geog))
            .limit(1)
        ).first()
        if row is not None and row[1] <= NEAREST_CITY_MAX_KM:
            city, distance_km = row[0], round(float(row[1]), 2)
            method = "nearest_city_centroid"
    governorate = db.get(Governorate, city.governorate_id) if city else containing(Governorate)
    if governorate is None and city is None:
        method = "none"
    return ResolveOut(
        governorate=_summary(governorate),
        city=_summary(city),
        district=_summary(district),
        neighborhood=_summary(neighborhood),
        method=method,
        approximate=method != "boundary",
        distance_km=distance_km,
    )


# --------------------------------------------------------------------------- admin


@router.post("/admin/locations/{level}", status_code=status.HTTP_201_CREATED)
def create_place(
    level: Level,
    body: PlaceCreate,
    principal: Principal = Depends(require_permission(Permission.LOCATIONS_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    parent = PARENT[level]
    if parent is None:
        raise AppError(
            "Governorates are fixed reference data", code="VALIDATION_ERROR", status_code=422
        )
    _get(db, parent[0], body.parent_id)
    model = MODELS[level]
    place = model(
        name_ar=body.name_ar.strip(),
        name_en=body.name_en.strip(),
        slug=body.slug or _slugify(body.name_en),
        is_active=True,
    )
    setattr(place, parent[1], body.parent_id)
    if body.centroid:
        place.centroid = make_point(body.centroid["lon"], body.centroid["lat"])
    if body.boundary:
        place.boundary = _geometry_sql(body.boundary.geometry)
        place.geometry_source = body.boundary.source.strip()
        if place.centroid is None:
            place.centroid = func.ST_PointOnSurface(_geometry_sql(body.boundary.geometry))
    db.add(place)
    try:
        db.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "A place with this slug already exists here", code="SLUG_TAKEN"
        ) from exc
    audit.record(
        db,
        "location.created",
        actor_id=principal.id,
        resource_type=level.value,
        resource_id=place.id,
        data={"name_en": place.name_en, "parent_id": str(body.parent_id)},
    )
    db.commit()
    return place_geojson(level, place.id, Response(), db)


@router.put("/admin/locations/{level}/{place_id}/boundary")
def set_boundary(
    level: Level,
    place_id: uuid.UUID,
    body: BoundaryIn,
    principal: Principal = Depends(require_permission(Permission.LOCATIONS_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    place = _get(db, level, place_id)
    shape = _geometry_sql(body.geometry)
    area, empty = db.execute(select(func.ST_Area(shape), func.ST_IsEmpty(shape))).one()
    if empty or not area:
        raise AppError(
            "Boundary has no area after repair", code="INVALID_GEOMETRY", status_code=422
        )
    place.boundary = shape
    place.geometry_source = body.source.strip()
    if place.centroid is None:
        place.centroid = func.ST_PointOnSurface(shape)
    audit.record(
        db,
        "location.boundary_set",
        actor_id=principal.id,
        resource_type=level.value,
        resource_id=place.id,
        data={"source": place.geometry_source},
    )
    db.commit()
    return place_geojson(level, place_id, Response(), db)


@router.delete(
    "/admin/locations/{level}/{place_id}/boundary", status_code=status.HTTP_204_NO_CONTENT
)
def clear_boundary(
    level: Level,
    place_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.LOCATIONS_MANAGE)),
    db: Session = Depends(get_db),
) -> None:
    place = _get(db, level, place_id)
    place.boundary = None
    place.geometry_source = None
    audit.record(
        db,
        "location.boundary_cleared",
        actor_id=principal.id,
        resource_type=level.value,
        resource_id=place.id,
    )
    db.commit()
