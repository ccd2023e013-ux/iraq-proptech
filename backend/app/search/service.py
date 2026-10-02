"""Search query builder: SearchFilters → one SQL query (+ one count).

Keyword search combines PostgreSQL full-text search (``search_vector``),
trigram word similarity (``search_text``, typo-tolerant, good for Arabic
spelling variants) and location names. Arabic text is normalized identically
on both sides by the ``normalize_ar`` SQL function.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, case, cast, func, literal, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.geo.models import City, District, Neighborhood
from app.geo.spatial import make_point
from app.properties.enums import PropertyStatus
from app.properties.models import Property, PropertyAmenity
from app.search.schemas import SearchFilters, SortOrder

MAX_RESULTS = 10_000  # deep pagination guard


def _name_matches(name_ar: Any, name_en: Any, q: str, nq: Any) -> Any:
    # strpos = plain substring match: user input is never treated as a LIKE pattern.
    return or_(
        func.strpos(func.normalize_ar(name_ar), nq) > 0,
        func.strpos(func.lower(name_en), q.lower()) > 0,
    )


def _keyword_condition(q: str) -> tuple[Any, Any]:
    """(where-condition, relevance-score) for a keyword query."""
    nq = func.normalize_ar(q)
    tsq = func.plainto_tsquery("simple", nq)
    fts = Property.search_vector.op("@@")(tsq)
    fuzzy = nq.op("<%")(Property.search_text)  # word_similarity >= pg_trgm threshold
    in_place = or_(
        Property.neighborhood_id.in_(
            select(Neighborhood.id).where(
                _name_matches(Neighborhood.name_ar, Neighborhood.name_en, q, nq)
            )
        ),
        Property.district_id.in_(
            select(District.id).where(_name_matches(District.name_ar, District.name_en, q, nq))
        ),
        Property.city_id.in_(
            select(City.id).where(_name_matches(City.name_ar, City.name_en, q, nq))
        ),
    )
    score = (
        func.ts_rank(Property.search_vector, tsq) * 2
        + func.word_similarity(nq, Property.search_text)
        + case((in_place, 0.5), else_=0.0)
    )
    return or_(fts, fuzzy, in_place), score


def build_query(filters: SearchFilters, *, public_only: bool = True) -> tuple[Select[Any], Any]:
    """Returns (query selecting Property, distance expression or None)."""
    stmt = select(Property).where(Property.deleted_at.is_(None))
    if public_only:
        stmt = stmt.where(Property.status == PropertyStatus.APPROVED)
    f = filters
    conditions: list[Any] = []
    if f.governorate_id:
        conditions.append(Property.governorate_id == f.governorate_id)
    if f.city_id:
        conditions.append(Property.city_id == f.city_id)
    if f.district_id:
        conditions.append(Property.district_id == f.district_id)
    if f.neighborhood_id:
        conditions.append(Property.neighborhood_id == f.neighborhood_id)
    if f.property_types:
        conditions.append(Property.property_type_code.in_(f.property_types))
    if f.purpose:
        conditions.append(Property.purpose == f.purpose.value)
    if f.rent_period:
        conditions.append(Property.rent_period == f.rent_period.value)
    if f.currency:
        conditions.append(Property.currency == f.currency.value)
    if f.min_price is not None:
        conditions.append(Property.price_amount >= f.min_price)
    if f.max_price is not None:
        conditions.append(Property.price_amount <= f.max_price)
    if f.min_area is not None:
        conditions.append(Property.area_m2 >= f.min_area)
    if f.max_area is not None:
        conditions.append(Property.area_m2 <= f.max_area)
    if f.bedrooms_min is not None:
        conditions.append(Property.bedrooms >= f.bedrooms_min)
    if f.bathrooms_min is not None:
        conditions.append(Property.bathrooms >= f.bathrooms_min)
    if f.furnishing:
        conditions.append(Property.furnishing == f.furnishing.value)
    if f.condition:
        conditions.append(Property.condition == f.condition.value)
    if f.verified_only:
        conditions.append(Property.verified_at.is_not(None))
    if f.exclude_demo:
        conditions.append(Property.is_demo.is_(False))
    if f.agency_id:
        conditions.append(Property.agency_id == f.agency_id)
    if f.agent_id:
        conditions.append(
            or_(
                Property.agent_id == f.agent_id,
                and_(Property.lister_id == f.agent_id, Property.agency_id.is_(None)),
            )
        )
    if f.posted_within_days:
        since = datetime.now(UTC) - timedelta(days=f.posted_within_days)
        conditions.append(Property.published_at >= since)
    if f.amenities:
        # Listing must have *all* requested amenities.
        has_all = (
            select(PropertyAmenity.property_id)
            .where(PropertyAmenity.amenity_code.in_(f.amenities))
            .group_by(PropertyAmenity.property_id)
            .having(func.count() == len(f.amenities))
        )
        conditions.append(Property.id.in_(has_all))

    # Spatial filters use the *public* point so results never reveal hidden locations.
    point_col = Property.display_location
    if f.bbox:
        envelope = func.ST_MakeEnvelope(f.bbox.west, f.bbox.south, f.bbox.east, f.bbox.north, 4326)
        conditions.append(func.ST_Intersects(point_col, envelope))  # index-assisted
    if f.polygon:
        ring = ", ".join(f"{lon} {lat}" for lon, lat in f.polygon)
        # Coordinates are validated floats; the WKT is bound as a parameter.
        polygon = func.ST_MakeValid(func.ST_GeomFromText(literal(f"POLYGON(({ring}))"), 4326))
        conditions.append(func.ST_Within(point_col, polygon))
    distance = None
    if f.radius_km is not None and f.near_lat is not None and f.near_lon is not None:
        centre = cast(make_point(f.near_lon, f.near_lat), _geography())
        geog = cast(point_col, _geography())
        conditions.append(func.ST_DWithin(geog, centre, f.radius_km * 1000))
        distance = func.ST_Distance(geog, centre)

    score = None
    if f.q:
        keyword, score = _keyword_condition(f.q.strip())
        conditions.append(keyword)

    stmt = stmt.where(*conditions)
    order: list[Any]
    # Amounts in different currencies are not comparable and are never converted:
    # without a currency filter, price sorts group by currency (IQD, then USD).
    by_currency = [Property.currency.asc()] if f.currency is None else []
    if f.sort == SortOrder.PRICE_ASC:
        order = [*by_currency, Property.price_amount.asc().nulls_last()]
    elif f.sort == SortOrder.PRICE_DESC:
        order = [*by_currency, Property.price_amount.desc().nulls_last()]
    elif f.sort == SortOrder.AREA_DESC:
        order = [Property.area_m2.desc().nulls_last()]
    elif f.sort == SortOrder.AREA_ASC:
        order = [Property.area_m2.asc().nulls_last()]
    elif f.sort == SortOrder.RELEVANCE and score is not None:
        order = [score.desc()]
    elif f.sort == SortOrder.DISTANCE and distance is not None:
        order = [distance.asc()]
    else:
        order = [Property.published_at.desc().nulls_last()]
    stmt = stmt.order_by(*order, Property.id)  # stable tie-breaker for pagination
    return stmt, distance


def _geography() -> Any:
    from geoalchemy2 import Geography

    return Geography(geometry_type="POINT", srid=4326)


def search(
    db: Session, filters: SearchFilters, *, offset: int, limit: int
) -> tuple[list[Property], int]:
    stmt, _ = build_query(filters)
    total = db.execute(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ).scalar_one()
    if offset >= MAX_RESULTS:
        return [], total
    rows = db.execute(stmt.offset(offset).limit(limit)).scalars()
    return list(rows), total
