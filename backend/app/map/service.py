"""Map data: search results as GeoJSON points, or server-side clusters when dense.

Every coordinate returned here is the listing's *public display location*
(already coarsened or replaced by a neighborhood centroid when the owner asked
for privacy). Listings with a HIDDEN location have no display point and never
appear on the map.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.properties.enums import MediaKind, ModerationState
from app.properties.models import Property, PropertyMedia
from app.search.schemas import SearchFilters
from app.search.service import build_query

POINT_LIMIT = 1500  # above this many matches in view, return clusters instead of points
MIN_ZOOM, MAX_ZOOM = 0, 22


def cluster_cell_degrees(zoom: int) -> float:
    """Grid cell size so one cluster covers roughly 60 px of a 256 px web-mercator tile."""
    zoom = max(MIN_ZOOM, min(MAX_ZOOM, zoom))
    return 360.0 / (2**zoom) / 4.0


def _money(value: Decimal | None) -> str | None:
    return None if value is None else f"{value:.2f}"


def map_features(db: Session, filters: SearchFilters, *, zoom: int) -> dict[str, Any]:
    """GeoJSON FeatureCollection for the map, with `meta` describing the mode."""
    base, _ = build_query(filters)
    matching = (
        base.order_by(None).where(Property.display_location.is_not(None)).subquery("matching")
    )
    total = db.execute(select(func.count()).select_from(matching)).scalar_one()

    if total > POINT_LIMIT:
        return _clusters(db, matching, total=total, zoom=zoom)

    cover = (
        select(PropertyMedia.id)
        .where(
            PropertyMedia.property_id == matching.c.id,
            PropertyMedia.kind == MediaKind.IMAGE,
            PropertyMedia.moderation == ModerationState.APPROVED,
        )
        .order_by(PropertyMedia.sort_order, PropertyMedia.created_at)
        .limit(1)
        .correlate(matching)
        .scalar_subquery()
    )
    rows = db.execute(
        select(
            matching.c.id,
            matching.c.title_ar,
            matching.c.title_en,
            matching.c.purpose,
            matching.c.property_type_code,
            matching.c.price_amount,
            matching.c.currency,
            matching.c.price_on_request,
            matching.c.rent_period,
            matching.c.bedrooms,
            matching.c.area_m2,
            matching.c.verified_at,
            matching.c.is_demo,
            matching.c.location_privacy,
            func.ST_X(matching.c.display_location).label("lon"),
            func.ST_Y(matching.c.display_location).label("lat"),
            cover.label("cover_id"),
        ).limit(POINT_LIMIT)
    ).all()
    features = [
        {
            "type": "Feature",
            "id": str(r.id),
            "geometry": {"type": "Point", "coordinates": [round(r.lon, 6), round(r.lat, 6)]},
            "properties": {
                "id": str(r.id),
                "title_ar": r.title_ar,
                "title_en": r.title_en,
                "purpose": r.purpose,
                "property_type_code": r.property_type_code,
                "price_amount": None if r.price_on_request else _money(r.price_amount),
                "currency": r.currency,
                "price_on_request": r.price_on_request,
                "rent_period": r.rent_period,
                "bedrooms": r.bedrooms,
                "area_m2": _money(r.area_m2),
                "verified": r.verified_at is not None,
                "is_demo": r.is_demo,
                "approximate": r.location_privacy != "EXACT",
                "cover_url": f"/api/v1/media/{r.cover_id}?variant=thumb" if r.cover_id else None,
            },
        }
        for r in rows
    ]
    return {
        "type": "FeatureCollection",
        "features": features,
        "meta": {"mode": "points", "total": total, "limit": POINT_LIMIT},
    }


def _clusters(db: Session, matching: Any, *, total: int, zoom: int) -> dict[str, Any]:
    cell = cluster_cell_degrees(zoom)
    point = matching.c.display_location
    snapped = func.ST_SnapToGrid(point, cell)
    rows = db.execute(
        select(
            func.count().label("n"),
            func.ST_X(func.ST_Centroid(func.ST_Collect(point))).label("lon"),
            func.ST_Y(func.ST_Centroid(func.ST_Collect(point))).label("lat"),
            func.ST_XMin(func.ST_Extent(point)).label("west"),
            func.ST_YMin(func.ST_Extent(point)).label("south"),
            func.ST_XMax(func.ST_Extent(point)).label("east"),
            func.ST_YMax(func.ST_Extent(point)).label("north"),
        ).group_by(snapped)
    ).all()
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(r.lon, 6), round(r.lat, 6)]},
            "properties": {
                "cluster": True,
                "point_count": r.n,
                "bbox": [r.west, r.south, r.east, r.north],
            },
        }
        for r in rows
    ]
    return {
        "type": "FeatureCollection",
        "features": features,
        "meta": {"mode": "clusters", "total": total, "limit": POINT_LIMIT, "cell_degrees": cell},
    }
