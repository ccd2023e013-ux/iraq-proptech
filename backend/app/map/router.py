"""/api/v1/map — search results for the map view (points or clusters)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.map import service
from app.search.router import query_filters
from app.search.schemas import SearchFilters

router = APIRouter(tags=["map"])


@router.get("/map/properties")
def map_properties(
    filters: SearchFilters = Depends(query_filters),
    zoom: int = Query(12, ge=service.MIN_ZOOM, le=service.MAX_ZOOM),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """GeoJSON FeatureCollection for the current map view.

    Accepts every search filter (use `bbox` for the viewport). Returns points
    (with enough data for a popup) or, when more than `meta.limit` listings
    match, server-side clusters sized for `zoom`.
    """
    return service.map_features(db, filters, zoom=zoom)
