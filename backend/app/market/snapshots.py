"""Record today's market snapshot (idempotent: re-running replaces today's rows)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Numeric, case, cast, delete, func, select
from sqlalchemy.orm import Session

from app.market.models import MarketSnapshot
from app.properties.enums import PropertyStatus
from app.properties.models import Property

MIN_SAMPLE = 5  # same floor as the report: no median below it is stored


def _rows(db: Session, scope_col: Any, include_demo: bool) -> list[Any]:
    priced = Property.price_on_request.is_(False) & Property.price_amount.is_not(None)
    per_m2 = Property.price_amount / func.nullif(cast(Property.area_m2, Numeric), 0)
    conditions = [Property.status == PropertyStatus.APPROVED, Property.deleted_at.is_(None)]
    if not include_demo:
        conditions.append(Property.is_demo.is_(False))
    segment = (Property.property_type_code, Property.purpose, Property.currency)
    keys = (*segment,) if scope_col is None else (scope_col, *segment)
    stmt = (
        select(
            *keys,
            func.count(Property.id),
            func.count(case((priced, 1))),
            func.percentile_cont(0.5).within_group(case((priced, Property.price_amount))),
            func.percentile_cont(0.5).within_group(case((priced, per_m2))),
        )
        .where(*conditions)
        .group_by(*keys)
    )
    rows = [tuple(r) for r in db.execute(stmt).all()]
    return rows if scope_col is not None else [(None, *r) for r in rows]


def _dec(value: Any) -> Decimal | None:
    return None if value is None else Decimal(value).quantize(Decimal("0.01"))


def record_snapshot(db: Session, day: date | None = None) -> dict[str, Any]:
    day = day or datetime.now(UTC).date()
    db.execute(delete(MarketSnapshot).where(MarketSnapshot.day == day))
    scopes = (
        ("iraq", None),
        ("governorate", Property.governorate_id),
        ("city", Property.city_id),
    )
    written = 0
    for include_demo in (True, False):
        for level, column in scopes:
            for scope, type_code, purpose, currency, count, priced, median, median_m2 in _rows(
                db, column, include_demo
            ):
                enough = priced >= MIN_SAMPLE
                db.add(
                    MarketSnapshot(
                        day=day,
                        scope_key="iraq" if level == "iraq" else f"{level}:{scope}",
                        property_type_code=type_code,
                        purpose=purpose,
                        currency=currency,
                        include_demo=include_demo,
                        active_listings=int(count),
                        priced_listings=int(priced),
                        median_price=_dec(median) if enough else None,
                        median_price_per_m2=_dec(median_m2) if enough else None,
                    )
                )
                written += 1
    db.commit()
    return {"day": day.isoformat(), "rows": written}
