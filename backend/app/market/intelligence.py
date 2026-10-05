"""Market Intelligence: what MAKAN's own data says about an area — and what it can't.

Every statement is one of:

* ``FACT``              a count or record on the platform ("127 active listings");
* ``OBSERVED``          a statistic computed from observed platform data, always with
                        its sample size and observation period (medians, changes);
* ``ESTIMATE``          a model/estimate built on top of observations (none yet here —
                        valuations live in property intelligence);
* ``AI_INTERPRETATION`` wording from an AI provider about the numbers above;
* ``SIMULATION``        scenario output (Stage 12; never mixed into this report).

Rules: no number is produced below a minimum sample; nothing is extrapolated
beyond the observation period; DEMO listings are flagged on every statement and
can be excluded; asking prices are never presented as transaction prices.
"""

from __future__ import annotations

import statistics
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from geoalchemy2 import Geography
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import and_, cast, func, select
from sqlalchemy.orm import Session, aliased

from app.ai import service as ai_service
from app.auth.deps import Principal
from app.core.errors import AppError, NotFoundError
from app.crm.models import Inquiry
from app.favorites import Favorite
from app.geo.models import City, District, Governorate
from app.market.models import MarketSnapshot
from app.properties.enums import PropertyStatus
from app.properties.models import (
    Property,
    PropertyPriceHistory,
    PropertyStatusHistory,
    PropertyType,
)

MarketKind = Literal["FACT", "OBSERVED", "ESTIMATE", "AI_INTERPRETATION", "SIMULATION"]
MarketOrigin = Literal["platform", "observed", "model", "ai", "scenario"]
MarketSection = Literal[
    "supply", "prices", "dynamics", "demand", "areas", "quality", "interpretation"
]
ALLOWED: dict[str, set[str]] = {
    "platform": {"FACT"},
    "observed": {"OBSERVED"},
    "model": {"ESTIMATE"},
    "ai": {"AI_INTERPRETATION"},
    "scenario": {"SIMULATION"},
}

MIN_SAMPLE = 5  # below this, medians are not reported
MIN_MONTH_SAMPLE = 5  # listings per month for a month to count in a trend
DEMAND_WINDOW_DAYS = 30
CLOSED_STATUSES = ("SOLD", "RENTED", "ARCHIVED", "EXPIRED")


class MarketStatement(BaseModel):
    kind: MarketKind
    origin: MarketOrigin
    section: MarketSection
    key: str
    params: dict[str, Any] = Field(default_factory=dict)
    text: str | None = None
    sample: int | None = Field(default=None, description="Observations behind the statement")
    demo: bool = Field(description="True when DEMO listings are part of the data")

    @model_validator(mode="after")
    def _kind_matches_origin(self) -> MarketStatement:
        if self.kind not in ALLOWED[self.origin]:
            raise ValueError(f"a statement from origin {self.origin!r} cannot be {self.kind}")
        if self.text is not None and self.origin != "ai":
            raise ValueError("free text is reserved for AI interpretations")
        if self.kind == "OBSERVED" and not self.sample:
            raise ValueError("observed statistics need their sample size")
        return self


class Unavailable(BaseModel):
    metric: str
    reason: str
    detail: dict[str, Any] = Field(default_factory=dict)


class Provenance(BaseModel):
    source: str
    coverage: str
    observation_from: date | None
    observation_to: date | None
    sample_listings: int
    includes_demo: bool
    demo_share: float
    methodology: list[str]
    confidence: Literal["none", "low", "medium", "high"]
    last_update: datetime


class SegmentRow(BaseModel):
    property_type_code: str
    type_ar: str
    type_en: str
    purpose: str
    currency: str
    listings: int
    median_price: str | None
    p25_price: str | None
    p75_price: str | None
    median_price_per_m2: str | None


class AreaRow(BaseModel):
    level: str
    id: uuid.UUID
    name_ar: str
    name_en: str | None
    active_listings: int
    median_price_per_m2: str | None
    currency: str | None
    sample: int


class SupplyPoint(BaseModel):
    day: date
    active_listings: int


class MarketReport(BaseModel):
    scope: dict[str, Any]
    provenance: Provenance
    statements: list[MarketStatement]
    segments: list[SegmentRow]
    areas: list[AreaRow]
    unavailable: list[Unavailable]
    supply_history: list[SupplyPoint] = Field(default_factory=list)
    disclaimer: str
    provider: str | None = None


# --- scope


def resolve_scope(
    db: Session,
    governorate_id: uuid.UUID | None,
    city_id: uuid.UUID | None,
    district_id: uuid.UUID | None,
) -> tuple[dict[str, Any], Any, str | None]:
    """(scope description, filter on Property, child level for the area breakdown)."""
    if district_id:
        d = db.get(District, district_id)
        if d is None:
            raise NotFoundError("Area not found", code="AREA_NOT_FOUND")
        return (
            {"level": "district", "id": str(d.id), "name_ar": d.name_ar, "name_en": d.name_en},
            Property.district_id == d.id,
            None,
        )
    if city_id:
        c = db.get(City, city_id)
        if c is None:
            raise NotFoundError("Area not found", code="AREA_NOT_FOUND")
        return (
            {"level": "city", "id": str(c.id), "name_ar": c.name_ar, "name_en": c.name_en},
            Property.city_id == c.id,
            "district",
        )
    if governorate_id:
        g = db.get(Governorate, governorate_id)
        if g is None:
            raise NotFoundError("Area not found", code="AREA_NOT_FOUND")
        return (
            {"level": "governorate", "id": str(g.id), "name_ar": g.name_ar, "name_en": g.name_en},
            Property.governorate_id == g.id,
            "city",
        )
    return ({"level": "iraq", "id": None, "name_ar": "العراق", "name_en": "Iraq"}, None, "city")


def _q(value: Decimal | float | None) -> str | None:
    return None if value is None else str(Decimal(value).quantize(Decimal("1")))


def _quartiles(values: list[Decimal]) -> tuple[Decimal, Decimal, Decimal]:
    q = statistics.quantiles(values, n=4, method="inclusive")
    return Decimal(q[0]), Decimal(statistics.median(values)), Decimal(q[2])


# --- report


def build_report(
    db: Session,
    principal: Principal | None,
    *,
    governorate_id: uuid.UUID | None = None,
    city_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    include_demo: bool = True,
    language: str = "ar",
    interpret: bool = True,
) -> MarketReport:
    scope, area_filter, child_level = resolve_scope(db, governorate_id, city_id, district_id)
    base = [Property.deleted_at.is_(None)]
    if area_filter is not None:
        base.append(area_filter)
    if not include_demo:
        base.append(Property.is_demo.is_(False))
    active = [*base, Property.status == PropertyStatus.APPROVED]
    now = datetime.now(UTC)

    rows = db.execute(
        select(
            Property.id,
            Property.property_type_code,
            Property.purpose,
            Property.currency,
            Property.price_amount,
            Property.price_on_request,
            Property.area_m2,
            Property.published_at,
            Property.is_demo,
        ).where(*active)
    ).all()
    n = len(rows)
    demo_n = sum(1 for r in rows if r.is_demo)
    demo = demo_n > 0
    statements: list[MarketStatement] = []
    unavailable: list[Unavailable] = []

    def fact(section: MarketSection, key: str, **params: Any) -> None:
        statements.append(
            MarketStatement(
                kind="FACT", origin="platform", section=section, key=key, params=params, demo=demo
            )
        )

    def observed(section: MarketSection, key: str, sample: int, **params: Any) -> None:
        statements.append(
            MarketStatement(
                kind="OBSERVED",
                origin="observed",
                section=section,
                key=key,
                params=params,
                sample=sample,
                demo=demo,
            )
        )

    # Supply (facts)
    fact("supply", "fact.active_listings", count=n, demo_count=demo_n)
    by_purpose: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for r in rows:
        by_purpose[r.purpose] = by_purpose.get(r.purpose, 0) + 1
        by_type[r.property_type_code] = by_type.get(r.property_type_code, 0) + 1
    if n:
        fact("supply", "fact.by_purpose", counts=by_purpose)
        fact("supply", "fact.by_type", counts=by_type)
    month_ago = now - timedelta(days=30)
    new_30 = sum(1 for r in rows if r.published_at and r.published_at >= month_ago)
    fact("supply", "fact.new_listings_30d", count=new_30)

    # Prices by segment (observed)
    types = {t.code: t for t in db.execute(select(PropertyType)).scalars()}
    groups: dict[tuple[str, str, str], list[Any]] = {}
    for r in rows:
        groups.setdefault((r.property_type_code, r.purpose, r.currency), []).append(r)
    segments: list[SegmentRow] = []
    for (code, purpose, currency), members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        prices = [
            Decimal(m.price_amount)
            for m in members
            if not m.price_on_request and m.price_amount is not None
        ]
        per_m2 = [
            Decimal(m.price_amount) / Decimal(m.area_m2)
            for m in members
            if not m.price_on_request and m.price_amount is not None and m.area_m2
        ]
        t = types.get(code)
        row = SegmentRow(
            property_type_code=code,
            type_ar=t.name_ar if t else code,
            type_en=t.name_en if t else code,
            purpose=purpose,
            currency=currency,
            listings=len(members),
            median_price=None,
            p25_price=None,
            p75_price=None,
            median_price_per_m2=None,
        )
        if len(prices) >= MIN_SAMPLE:
            p25, med, p75 = _quartiles(prices)
            row.median_price, row.p25_price, row.p75_price = _q(med), _q(p25), _q(p75)
            observed(
                "prices",
                "observed.segment_median",
                sample=len(prices),
                type_code=code,
                type_ar=row.type_ar,
                type_en=row.type_en,
                purpose=purpose,
                currency=currency,
                median=row.median_price,
                p25=row.p25_price,
                p75=row.p75_price,
            )
        if len(per_m2) >= MIN_SAMPLE:
            row.median_price_per_m2 = _q(statistics.median(per_m2))
        segments.append(row)
    if not any(s.median_price for s in segments):
        unavailable.append(
            Unavailable(
                metric="segment_medians",
                reason="sample_too_small",
                detail={"minimum": MIN_SAMPLE},
            )
        )

    # Trend: median asking price per m² by listing month, same segment, only with enough months
    trend_done = False
    if groups:
        (code, purpose, currency), members = max(groups.items(), key=lambda kv: len(kv[1]))
        months: dict[str, list[Decimal]] = {}
        for m in members:
            if (
                m.published_at
                and m.price_amount is not None
                and m.area_m2
                and not m.price_on_request
            ):
                key = m.published_at.strftime("%Y-%m")
                months.setdefault(key, []).append(Decimal(m.price_amount) / Decimal(m.area_m2))
        usable = {k: v for k, v in sorted(months.items()) if len(v) >= MIN_MONTH_SAMPLE}
        if len(usable) >= 2:
            first_k, last_k = next(iter(usable)), list(usable)[-1]
            first_v = Decimal(statistics.median(usable[first_k]))
            last_v = Decimal(statistics.median(usable[last_k]))
            change = float((last_v - first_v) / first_v * 100) if first_v else 0.0
            observed(
                "dynamics",
                "observed.price_per_m2_change",
                sample=sum(len(v) for v in usable.values()),
                type_code=code,
                type_ar=types[code].name_ar if code in types else code,
                type_en=types[code].name_en if code in types else code,
                purpose=purpose,
                currency=currency,
                from_month=first_k,
                to_month=last_k,
                months=len(usable),
                change_pct=round(change, 1),
            )
            trend_done = True
        if not trend_done:
            unavailable.append(
                Unavailable(
                    metric="price_trend",
                    reason="observation_period_too_short",
                    detail={
                        "months_with_enough_listings": len(usable),
                        "needed": 2,
                        "minimum_per_month": MIN_MONTH_SAMPLE,
                    },
                )
            )

    # Price changes on listings (observed from price history)
    ids = [r.id for r in rows]
    if ids:
        hist = db.execute(
            select(PropertyPriceHistory.property_id, PropertyPriceHistory.price_amount)
            .where(
                PropertyPriceHistory.property_id.in_(ids),
                PropertyPriceHistory.price_amount.is_not(None),
            )
            .order_by(PropertyPriceHistory.property_id, PropertyPriceHistory.changed_at)
        ).all()
        series: dict[uuid.UUID, list[Decimal]] = {}
        for pid, amount in hist:
            series.setdefault(pid, []).append(Decimal(amount))
        changes = [
            float((v[-1] - v[0]) / v[0] * 100) for v in series.values() if len(v) > 1 and v[0]
        ]
        fact("dynamics", "fact.listings_with_price_change", count=len(changes), of=n)
        if len(changes) >= MIN_SAMPLE:
            observed(
                "dynamics",
                "observed.median_price_change",
                sample=len(changes),
                change_pct=round(statistics.median(changes), 1),
            )
        else:
            unavailable.append(
                Unavailable(
                    metric="price_changes",
                    reason="sample_too_small",
                    detail={"listings_with_changes": len(changes), "minimum": MIN_SAMPLE},
                )
            )

    # Time on market: closed listings (approval → closing status)
    closed_rows = db.execute(
        select(Property.id, Property.published_at, func.max(PropertyStatusHistory.changed_at))
        .join(PropertyStatusHistory, PropertyStatusHistory.property_id == Property.id)
        .where(
            *base,
            Property.published_at.is_not(None),
            PropertyStatusHistory.to_status.in_(CLOSED_STATUSES),
        )
        .group_by(Property.id, Property.published_at)
    ).all()
    durations = [
        (closed - published).days
        for _, published, closed in closed_rows
        if closed and published and closed >= published
    ]
    if len(durations) >= MIN_SAMPLE:
        observed(
            "dynamics",
            "observed.median_days_on_market",
            sample=len(durations),
            days=int(statistics.median(durations)),
        )
    else:
        unavailable.append(
            Unavailable(
                metric="time_on_market",
                reason="too_few_closed_listings",
                detail={"closed_listings": len(durations), "minimum": MIN_SAMPLE},
            )
        )
    active_ages = [(now - r.published_at).days for r in rows if r.published_at]
    if len(active_ages) >= MIN_SAMPLE:
        observed(
            "dynamics",
            "observed.median_active_age",
            sample=len(active_ages),
            days=int(statistics.median(active_ages)),
        )

    # Demand proxies (facts over the window)
    since = now - timedelta(days=DEMAND_WINDOW_DAYS)
    if ids:
        inquiries = db.execute(
            select(func.count()).where(Inquiry.property_id.in_(ids), Inquiry.created_at >= since)
        ).scalar_one()
        favorites = db.execute(
            select(func.count()).where(Favorite.property_id.in_(ids), Favorite.created_at >= since)
        ).scalar_one()
        from app.analytics.models import PropertyViewDaily

        views = db.execute(
            select(func.coalesce(func.sum(PropertyViewDaily.views), 0)).where(
                PropertyViewDaily.property_id.in_(ids),
                PropertyViewDaily.day >= since.date(),
            )
        ).scalar_one()
        fact(
            "demand",
            "fact.demand_30d",
            views=int(views),
            inquiries=int(inquiries),
            favorites=int(favorites),
            days=DEMAND_WINDOW_DAYS,
        )

    # Supply over time: only from recorded daily snapshots (never back-filled)
    history: list[SupplyPoint] = []
    if scope["level"] == "district":
        unavailable.append(Unavailable(metric="supply_trend", reason="not_recorded_for_districts"))
    else:
        scope_key = "iraq" if scope["level"] == "iraq" else f"{scope['level']}:{scope['id']}"
        history = [
            SupplyPoint(day=day, active_listings=int(total))
            for day, total in db.execute(
                select(MarketSnapshot.day, func.sum(MarketSnapshot.active_listings))
                .where(
                    MarketSnapshot.scope_key == scope_key,
                    MarketSnapshot.include_demo.is_(include_demo),
                )
                .group_by(MarketSnapshot.day)
                .order_by(MarketSnapshot.day)
            ).all()
        ]
        if len(history) >= 2:
            observed(
                "supply",
                "observed.supply_change",
                sample=len(history),
                from_day=history[0].day.isoformat(),
                to_day=history[-1].day.isoformat(),
                from_count=history[0].active_listings,
                to_count=history[-1].active_listings,
            )
        else:
            unavailable.append(
                Unavailable(
                    metric="supply_trend",
                    reason="snapshots_too_few",
                    detail={
                        "days_recorded": len(history),
                        "first_day": history[0].day.isoformat() if history else None,
                    },
                )
            )

    # Possible duplicate listings (same type/purpose/currency/price, area within 2%, < 200 m)
    if ids and n <= 3000:
        a, b = aliased(Property), aliased(Property)
        geog = Geography(geometry_type="POINT", srid=4326)
        pairs = db.execute(
            select(func.count())
            .select_from(a)
            .join(
                b,
                and_(
                    a.id < b.id,
                    a.property_type_code == b.property_type_code,
                    a.purpose == b.purpose,
                    a.currency == b.currency,
                    a.price_amount == b.price_amount,
                    func.abs(a.area_m2 - b.area_m2) <= a.area_m2 * Decimal("0.02"),
                    func.ST_DWithin(
                        cast(a.display_location, geog), cast(b.display_location, geog), 200
                    ),
                ),
            )
            .where(a.id.in_(ids), b.id.in_(ids))
        ).scalar_one()
        fact("quality", "fact.possible_duplicate_pairs", pairs=int(pairs))

    # Area breakdown (observed per child area)
    areas: list[AreaRow] = []
    if child_level:
        model = District if child_level == "district" else City
        column = Property.district_id if child_level == "district" else Property.city_id
        area_rows: dict[uuid.UUID, list[Any]] = {}
        for r in db.execute(
            select(
                column,
                Property.price_amount,
                Property.area_m2,
                Property.currency,
                Property.price_on_request,
            ).where(*active, column.is_not(None), Property.purpose == "SALE")
        ).all():
            area_rows.setdefault(r[0], []).append(r)
        counts = dict(
            db.execute(
                select(column, func.count()).where(*active, column.is_not(None)).group_by(column)
            ).all()
        )
        places = {
            p.id: p for p in db.execute(select(model).where(model.id.in_(list(counts)))).scalars()
        }
        for area_id, count in sorted(counts.items(), key=lambda kv: -kv[1])[:30]:
            place = places.get(area_id)
            if place is None:
                continue
            sale = area_rows.get(area_id, [])
            by_cur: dict[str, list[Decimal]] = {}
            for _, price, m2, cur, por in sale:
                if price is not None and m2 and not por:
                    by_cur.setdefault(cur, []).append(Decimal(price) / Decimal(m2))
            cur, values = max(by_cur.items(), key=lambda kv: len(kv[1]), default=(None, []))
            median = _q(statistics.median(values)) if len(values) >= MIN_SAMPLE else None
            areas.append(
                AreaRow(
                    level=child_level,
                    id=area_id,
                    name_ar=place.name_ar,
                    name_en=place.name_en,
                    active_listings=int(count),
                    median_price_per_m2=median,
                    currency=cur if median else None,
                    sample=len(values),
                )
            )
        if areas:
            observed(
                "areas",
                "observed.area_breakdown",
                sample=n,
                level=child_level,
                areas=len(areas),
            )

    # Provenance
    published = [r.published_at for r in rows if r.published_at]
    reported = [s for s in statements if s.kind == "OBSERVED"]
    confidence: Literal["none", "low", "medium", "high"] = (
        "none" if n == 0 else "low" if n < 30 or demo else "medium" if n < 200 else "high"
    )
    provenance = Provenance(
        source="MAKAN platform listings (asking prices, not transaction prices)",
        coverage=f"{scope['level']}: {scope['name_en'] or scope['name_ar']}",
        observation_from=min(published).date() if published else None,
        observation_to=max(published).date() if published else None,
        sample_listings=n,
        includes_demo=demo,
        demo_share=round(demo_n / n, 3) if n else 0.0,
        methodology=[
            f"medians and quartiles only with at least {MIN_SAMPLE} listings",
            "currencies are never converted or mixed",
            "trend compares monthly medians of one segment, only months with "
            f"{MIN_MONTH_SAMPLE}+ listings",
            "demand proxies are platform views, saves and inquiries, not market demand",
            "supply over time comes from daily snapshots recorded going forward, never back-filled",
        ],
        confidence=confidence,
        last_update=now,
    )

    provider: str | None = None
    if interpret and reported:
        facts = {
            "scope_ar": scope["name_ar"],
            "scope_en": scope["name_en"],
            "active_listings": n,
            "includes_demo": demo,
        }
        top = next((s for s in statements if s.key == "observed.segment_median"), None)
        if top:
            facts.update(
                segment_type_ar=top.params["type_ar"],
                segment_type_en=top.params["type_en"],
                segment_purpose=top.params["purpose"],
                segment_median=f"{int(top.params['median']):,}",
                segment_currency=top.params["currency"],
                segment_sample=top.sample,
            )
        try:
            data, row = ai_service.generate(
                db,
                principal,
                feature="market.interpretation",
                task="market.interpretation",
                system=(
                    "You describe Iraqi property market data. Use only the facts given. Say "
                    "'based on the available data'. Never predict prices, never promise returns, "
                    "never call listing prices transaction prices. If includes_demo is true, say "
                    "the data is demonstration data."
                ),
                instructions="Two short sentences in plain words.",
                facts=facts,
                output_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
                validate=ai_service._require_str_fields("text"),
                language=language,
            )
        except AppError as exc:
            if exc.code != "AI_QUOTA_EXCEEDED":
                raise
            unavailable.append(Unavailable(metric="ai_interpretation", reason="ai_quota_reached"))
        else:
            provider = row.provider
            statements.append(
                MarketStatement(
                    kind="AI_INTERPRETATION",
                    origin="ai",
                    section="interpretation",
                    key="ai.text",
                    text=str(data["text"])[:800],
                    demo=demo,
                )
            )

    return MarketReport(
        scope=scope,
        provenance=provenance,
        statements=statements,
        segments=segments,
        areas=areas,
        unavailable=unavailable,
        supply_history=history,
        disclaimer=(
            "Asking prices from listings on MAKAN, not transaction prices or valuations. "
            "No statement here predicts future prices or guarantees returns."
        ),
        provider=provider,
    )


def ensure_scope_args(
    governorate_id: uuid.UUID | None, city_id: uuid.UUID | None, district_id: uuid.UUID | None
) -> None:
    if sum(x is not None for x in (governorate_id, city_id, district_id)) > 1:
        raise AppError(
            "Give one of governorate_id, city_id or district_id",
            code="VALIDATION_ERROR",
            status_code=422,
        )


__all__ = ["MarketReport", "MarketStatement", "build_report", "ensure_scope_args"]
