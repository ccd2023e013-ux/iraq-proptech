"""/api/v1/search/properties — GET (query string) and POST (JSON body)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.analytics import service as analytics
from app.core.errors import AppError
from app.core.pagination import PageParams, page_params
from app.db.session import get_db
from app.properties.presenter import to_cards
from app.properties.schemas import PropertyCard
from app.search import service
from app.search.schemas import SearchFilters

router = APIRouter(tags=["search"])


class SearchResult(BaseModel):
    items: list[PropertyCard]
    total: int
    page: int
    page_size: int
    filters: SearchFilters


def validate_filters(raw: dict[str, Any]) -> SearchFilters:
    try:
        return SearchFilters.model_validate(raw)
    except ValidationError as exc:
        details = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")}
            for e in exc.errors(include_url=False, include_context=False)
        ]
        raise AppError(
            "Invalid search filters", code="VALIDATION_ERROR", status_code=422, details=details
        ) from exc


def _parse_bbox(value: str | None) -> dict[str, float] | None:
    if not value:
        return None
    try:
        west, south, east, north = (float(v) for v in value.split(","))
    except ValueError as exc:
        raise AppError("bbox must be 'west,south,east,north'", code="VALIDATION_ERROR") from exc
    return {"west": west, "south": south, "east": east, "north": north}


def _parse_polygon(value: str | None) -> list[tuple[float, float]] | None:
    if not value:
        return None
    try:
        return [
            (float(lon), float(lat))
            for lon, lat in (pair.split(",") for pair in value.split(";") if pair)
        ]
    except ValueError as exc:
        raise AppError("polygon must be 'lon,lat;lon,lat;...'", code="VALIDATION_ERROR") from exc


def _run(db: Session, filters: SearchFilters, params: PageParams) -> SearchResult:
    rows, total = service.search(db, filters, offset=params.offset, limit=params.page_size)
    if params.page == 1:
        analytics.record_search(db, filters, total)
    return SearchResult(
        items=to_cards(db, rows),
        total=total,
        page=params.page,
        page_size=params.page_size,
        filters=filters,
    )


def query_filters(
    q: Annotated[str | None, Query(max_length=200)] = None,
    governorate_id: uuid.UUID | None = None,
    city_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    neighborhood_id: uuid.UUID | None = None,
    property_types: Annotated[list[str] | None, Query(max_length=20)] = None,
    purpose: str | None = None,
    rent_period: str | None = None,
    currency: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    min_area: Decimal | None = None,
    max_area: Decimal | None = None,
    bedrooms_min: int | None = None,
    bathrooms_min: int | None = None,
    amenities: Annotated[list[str] | None, Query(max_length=30)] = None,
    furnishing: str | None = None,
    condition: str | None = None,
    verified_only: bool = False,
    exclude_demo: bool = False,
    agency_id: uuid.UUID | None = None,
    agent_id: uuid.UUID | None = None,
    posted_within_days: int | None = None,
    bbox: Annotated[str | None, Query(max_length=120, description="west,south,east,north")] = None,
    near_lat: float | None = None,
    near_lon: float | None = None,
    radius_km: float | None = None,
    polygon: Annotated[
        str | None, Query(max_length=8000, description="lon,lat;lon,lat;...")
    ] = None,
    sort: str = "newest",
) -> SearchFilters:
    """FastAPI dependency: search filters from the query string (shared with /map)."""
    raw: dict[str, Any] = {
        "q": q,
        "governorate_id": governorate_id,
        "city_id": city_id,
        "district_id": district_id,
        "neighborhood_id": neighborhood_id,
        "property_types": property_types or [],
        "purpose": purpose,
        "rent_period": rent_period,
        "currency": currency,
        "min_price": min_price,
        "max_price": max_price,
        "min_area": min_area,
        "max_area": max_area,
        "bedrooms_min": bedrooms_min,
        "bathrooms_min": bathrooms_min,
        "amenities": amenities or [],
        "furnishing": furnishing,
        "condition": condition,
        "verified_only": verified_only,
        "exclude_demo": exclude_demo,
        "agency_id": agency_id,
        "agent_id": agent_id,
        "posted_within_days": posted_within_days,
        "bbox": _parse_bbox(bbox),
        "near_lat": near_lat,
        "near_lon": near_lon,
        "radius_km": radius_km,
        "polygon": _parse_polygon(polygon),
        "sort": sort,
    }
    return validate_filters({k: v for k, v in raw.items() if v is not None})


@router.get("/search/properties", response_model=SearchResult)
def search_get(
    filters: SearchFilters = Depends(query_filters),
    params: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
) -> SearchResult:
    return _run(db, filters, params)


@router.post("/search/properties", response_model=SearchResult)
def search_post(
    body: dict[str, Any],
    params: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
) -> SearchResult:
    """Same search with a JSON body (polygons, saved searches, AI-generated filters)."""
    return _run(db, validate_filters(body), params)
