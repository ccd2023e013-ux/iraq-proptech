"""/api/v1/market — public market readings computed from listings on the platform.

Data class is always ``platform`` (asking prices of public listings, not
transactions) and the response says whether DEMO listings are included, so
the UI can never present synthetic data as market truth. Medians, not means:
robust to outliers. Currencies are never mixed or converted.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import Numeric, case, cast, func, select
from sqlalchemy.orm import Session

from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.geo.models import City, Governorate
from app.properties.enums import PropertyStatus
from app.properties.models import Property

router = APIRouter(
    tags=["market"], dependencies=[Depends(rate_limit("market", limit=120, window=60))]
)

CACHE = "public, max-age=300"


def _public() -> list[Any]:
    return [Property.status == PropertyStatus.APPROVED, Property.deleted_at.is_(None)]


def _dec(value: Any) -> str | None:
    return None if value is None else str(Decimal(value).quantize(Decimal("0.01")))


@router.get("/market/cities")
def market_cities(response: Response, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Cities with public listings, most listings first."""
    rows = (
        db.execute(
            select(
                City.id,
                City.slug,
                City.name_ar,
                City.name_en,
                Governorate.code,
                func.count(Property.id),
                func.bool_or(Property.is_demo),
            )
            .join(Property, Property.city_id == City.id)
            .join(Governorate, Governorate.id == City.governorate_id)
            .where(*_public())
            .group_by(City.id, Governorate.code)
            .order_by(func.count(Property.id).desc(), City.name_en)
        )
        .tuples()
        .all()
    )
    response.headers["Cache-Control"] = CACHE
    return [
        {
            "city_id": str(cid),
            "slug": slug,
            "name_ar": name_ar,
            "name_en": name_en,
            "governorate_code": gov,
            "listings": count,
            "includes_demo": bool(demo),
        }
        for cid, slug, name_ar, name_en, gov, count, demo in rows
    ]


@router.get("/market/summary")
def market_summary(
    response: Response,
    city_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Count and median asking price (and price per m²) by type, purpose and currency."""
    conditions = _public()
    if city_id is not None:
        conditions.append(Property.city_id == city_id)
    priced = Property.price_on_request.is_(False) & Property.price_amount.is_not(None)
    per_m2 = Property.price_amount / func.nullif(cast(Property.area_m2, Numeric), 0)
    rows = (
        db.execute(
            select(
                Property.property_type_code,
                Property.purpose,
                Property.currency,
                func.count(Property.id),
                func.percentile_cont(0.5).within_group(case((priced, Property.price_amount))),
                func.percentile_cont(0.5).within_group(case((priced, per_m2))),
                func.bool_or(Property.is_demo),
            )
            .where(*conditions)
            .group_by(Property.property_type_code, Property.purpose, Property.currency)
            .order_by(func.count(Property.id).desc())
        )
        .tuples()
        .all()
    )
    response.headers["Cache-Control"] = CACHE
    segments = [
        {
            "property_type_code": type_code,
            "purpose": purpose,
            "currency": currency,
            "listings": count,
            "median_price": _dec(median),
            "median_price_per_m2": _dec(median_m2),
        }
        for type_code, purpose, currency, count, median, median_m2, _ in rows
    ]
    return {
        "city_id": str(city_id) if city_id else None,
        "data_class": "platform",
        "basis": "asking prices of public listings (not transactions)",
        "includes_demo": any(r[6] for r in rows),
        "listings": sum(s["listings"] for s in segments),
        "segments": segments,
        "generated_at": datetime.now(UTC).isoformat(),
    }
