"""Side-by-side comparison of 2–4 public listings.

Only declared facts are compared. Derived values (price per m²) are computed
per listing in that listing's own currency; listings in different currencies
are never ranked against each other.
"""

from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import Principal, get_optional_principal
from app.core.errors import AppError
from app.db.session import get_db
from app.properties.models import Property
from app.properties.presenter import to_out
from app.properties.schemas import PropertyOut

router = APIRouter(tags=["properties"])

COMPARED_FIELDS = [
    "property_type_code",
    "purpose",
    "price_amount",
    "currency",
    "area_m2",
    "land_area_m2",
    "bedrooms",
    "bathrooms",
    "floors",
    "year_built",
    "condition",
    "furnishing",
    "ownership_document",
    "verified",
]


class ComparisonRow(BaseModel):
    field: str
    values: list[str | None]
    differs: bool


class ComparisonOut(BaseModel):
    items: list[PropertyOut]
    price_per_m2: list[str | None]
    rows: list[ComparisonRow]
    same_currency: bool
    cheapest_per_m2_id: uuid.UUID | None
    amenities_common: list[str]


def _text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return str(value)


def _per_m2(p: PropertyOut) -> Decimal | None:
    if p.price_on_request or p.price_amount is None or not p.area_m2:
        return None
    return (Decimal(p.price_amount) / Decimal(p.area_m2)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


@router.get("/properties/compare", response_model=ComparisonOut)
def compare(
    ids: str = Query(description="2–4 comma-separated listing IDs", max_length=200),
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> ComparisonOut:
    try:
        wanted = list(dict.fromkeys(uuid.UUID(v.strip()) for v in ids.split(",") if v.strip()))
    except ValueError as exc:
        raise AppError("ids must be UUIDs", code="VALIDATION_ERROR", status_code=422) from exc
    if not 2 <= len(wanted) <= 4:
        raise AppError("Compare 2 to 4 listings", code="VALIDATION_ERROR", status_code=422)
    found = {
        p.id: p
        for p in db.execute(
            select(Property).where(Property.id.in_(wanted), Property.deleted_at.is_(None))
        ).scalars()
        if p.is_public
    }
    if len(found) != len(wanted):
        raise AppError(
            "Some listings are not available", code="PROPERTY_NOT_FOUND", status_code=404
        )
    items = [to_out(db, found[i], principal) for i in wanted]
    rows = []
    for field in COMPARED_FIELDS:
        values = [_text(getattr(item, field, None)) for item in items]
        rows.append(ComparisonRow(field=field, values=values, differs=len(set(values)) > 1))
    per_m2 = [_per_m2(i) for i in items]
    currencies = {i.currency for i in items}
    same_currency = len(currencies) == 1
    cheapest = None
    if same_currency:
        priced = [(v, i.id) for v, i in zip(per_m2, items, strict=True) if v is not None]
        if len(priced) >= 2:
            cheapest = min(priced)[1]
    common = sorted(set.intersection(*(set(i.amenities) for i in items)))
    return ComparisonOut(
        items=items,
        price_per_m2=[_text(v) for v in per_m2],
        rows=rows,
        same_currency=same_currency,
        cheapest_per_m2_id=cheapest,
        amenities_common=common,
    )
