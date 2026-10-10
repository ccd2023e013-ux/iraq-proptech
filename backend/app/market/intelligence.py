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
beyond the observation period or back-filled; DEMO listings are flagged on every
statement whose data contains them and can be excluded; currencies are never
mixed; asking prices are never presented as sold/transaction prices (MAKAN does
not collect transaction prices, and says so). Every statement carries its own
provenance (source, period, method); the report adds coverage and confidence.
"""

from __future__ import annotations

import re
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

MIN_SAMPLE = 5  # below this, no statistic is reported
MIN_MONTH_SAMPLE = 5  # listings per month for a month to count in a trend
DEMAND_WINDOW_DAYS = 30
# Lister-reported outcomes only; ARCHIVED/EXPIRED are withdrawals, not sales.
MARKED_CLOSED = ("SOLD", "RENTED")
# Listings that were taken down or never went public stay out of every cohort.
NEVER_PUBLIC = ("DRAFT", "PENDING_REVIEW", "REJECTED", "SUSPENDED")
DUPLICATE_SCAN_LIMIT = 3000
STALE_AFTER_DAYS = 90  # newest listing older than this lowers confidence

MarketSource = Literal[
    "listings",  # current listings (asking prices, counts)
    "price_history",  # recorded asking-price changes
    "status_history",  # lister-reported status changes (sold/rented)
    "interest",  # views, saves, inquiries on MAKAN
    "snapshots",  # daily market snapshots, recorded going forward
    "ai",  # AI provider wording
]


class MarketStatement(BaseModel):
    kind: MarketKind
    origin: MarketOrigin
    section: MarketSection
    key: str
    params: dict[str, Any] = Field(default_factory=dict)
    text: str | None = None
    sample: int | None = Field(default=None, description="Observations behind the statement")
    demo: bool = Field(description="True when DEMO listings are part of the data")
    # per-statement provenance
    source: MarketSource
    method: str = Field(description="Method key, e.g. 'count', 'median', 'median_change'")
    period_from: date | None = None
    period_to: date | None = None

    @model_validator(mode="after")
    def _kind_matches_origin(self) -> MarketStatement:
        if self.kind not in ALLOWED[self.origin]:
            raise ValueError(f"a statement from origin {self.origin!r} cannot be {self.kind}")
        if self.text is not None and self.origin != "ai":
            raise ValueError("free text is reserved for AI interpretations")
        if (self.origin == "ai") != (self.source == "ai"):
            raise ValueError("only AI interpretations come from the AI source")
        if self.kind == "OBSERVED":
            if not self.sample or self.sample < MIN_SAMPLE:
                raise ValueError(f"observed statistics need a sample of at least {MIN_SAMPLE}")
            if self.period_from is None or self.period_to is None:
                raise ValueError("observed statistics need their observation period")
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
    confidence_reasons: list[str]
    last_update: datetime
    newest_listing: date | None = None


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


class AreaBasis(BaseModel):
    """The one segment the area comparison uses, so bars are comparable."""

    property_type_code: str
    type_ar: str
    type_en: str
    purpose: str
    currency: str


class SupplyPoint(BaseModel):
    day: date
    active_listings: int


class MarketReport(BaseModel):
    scope: dict[str, Any]
    provenance: Provenance
    statements: list[MarketStatement]
    segments: list[SegmentRow]
    areas: list[AreaRow]
    areas_basis: AreaBasis | None = None
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

# Words an AI interpretation may never use: forecasts, promises, advice, and any
# claim that listing prices are sale/transaction prices. Matched case-insensitively
# on the normalized text; a hit rejects the output and the template is used.
AI_FORBIDDEN = (
    # forecasts / predictions
    "will rise",
    "will fall",
    "will increase",
    "will decrease",
    "will grow",
    "expected to",
    "forecast",
    "predict",
    "outlook",
    "next year",
    "next month",
    "سيرتفع",
    "سينخفض",
    "سترتفع",
    "ستنخفض",
    "سيزداد",
    "يتوقع",
    "متوقع",
    "توقعات",
    "العام المقبل",
    "الشهر المقبل",
    # promises / advice
    "guarantee",
    "return on investment",
    "roi",
    "profit",
    "good investment",
    "best time to buy",
    "you should buy",
    "مضمون",
    "ارباح",
    "ربح",
    "عائد",
    "فرصه استثماريه",
    "انصح",
    # transaction-price claims
    "sold for",
    "sale price",
    "transaction price",
    "selling price",
    "actual price",
    "سعر البيع الفعلي",
    "سعر الصفقه",
    "بيعت",
)


def _forbidden_hits(text: str) -> list[str]:
    """Latin phrases match whole words; Arabic ones match inside words (attached
    prefixes such as و/ال/ب are common)."""
    from app.ai.nlsearch import normalize

    norm = normalize(text)
    hits = []
    for phrase in AI_FORBIDDEN:
        p = normalize(phrase)
        if p.isascii():
            if re.search(rf"\b{re.escape(p)}\b", norm):
                hits.append(phrase)
        elif p in norm:
            hits.append(phrase)
    return hits


def _ai_check(data: dict[str, Any]) -> list[str]:
    errors = ai_service._require_str_fields("text")(data)
    if errors:
        return errors
    return [f"forbidden_claim:{w}" for w in _forbidden_hits(str(data["text"]))]


def _confidence(
    n: int, demo_n: int, newest: datetime | None, now: datetime
) -> tuple[Literal["none", "low", "medium", "high"], list[str]]:
    """Confidence from sample size, data quality (demo share) and freshness."""
    if n == 0:
        return "none", ["no_listings"]
    reasons: list[str] = []
    level = 3 if n >= 200 else 2 if n >= 30 else 1
    reasons.append("large_sample" if n >= 200 else "medium_sample" if n >= 30 else "small_sample")
    if demo_n:
        level = 1
        reasons.append("demo_data")
    if newest is None or (now - newest).days > STALE_AFTER_DAYS:
        level = min(level, 1)
        reasons.append("stale")
    reasons.append("asking_prices_only")
    levels: tuple[Literal["low", "medium", "high"], ...] = ("low", "medium", "high")
    return levels[level - 1], reasons


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
    today = now.date()

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
    published = [r.published_at for r in rows if r.published_at]
    oldest = min(published).date() if published else None
    newest_at = max(published) if published else None
    statements: list[MarketStatement] = []
    unavailable: list[Unavailable] = []

    def fact(
        section: MarketSection,
        key: str,
        *,
        source: MarketSource = "listings",
        method: str = "count",
        period: tuple[date | None, date | None] = (None, today),
        has_demo: bool | None = None,
        **params: Any,
    ) -> None:
        statements.append(
            MarketStatement(
                kind="FACT",
                origin="platform",
                section=section,
                key=key,
                params=params,
                demo=demo if has_demo is None else has_demo,
                source=source,
                method=method,
                period_from=period[0],
                period_to=period[1],
            )
        )

    def observed(
        section: MarketSection,
        key: str,
        sample: int,
        *,
        source: MarketSource,
        method: str,
        period: tuple[date | None, date | None],
        has_demo: bool | None = None,
        **params: Any,
    ) -> None:
        statements.append(
            MarketStatement(
                kind="OBSERVED",
                origin="observed",
                section=section,
                key=key,
                params=params,
                sample=sample,
                demo=demo if has_demo is None else has_demo,
                source=source,
                method=method,
                period_from=period[0],
                period_to=period[1],
            )
        )

    # MAKAN has no transaction data: say so every time, never imply it.
    unavailable.append(Unavailable(metric="transaction_prices", reason="not_collected"))

    # --- Supply (facts about current listings)
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
    new_30 = [r for r in rows if r.published_at and r.published_at >= month_ago]
    fact(
        "supply",
        "fact.new_listings_30d",
        period=(month_ago.date(), today),
        has_demo=any(r.is_demo for r in new_30),
        count=len(new_30),
    )

    # --- Asking prices by segment (type x purpose x currency; never mixed)
    types = {t.code: t for t in db.execute(select(PropertyType)).scalars()}
    groups: dict[tuple[str, str, str], list[Any]] = {}
    for r in rows:
        groups.setdefault((r.property_type_code, r.purpose, r.currency), []).append(r)
    segments: list[SegmentRow] = []
    for (code, purpose, currency), members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        priced = [m for m in members if not m.price_on_request and m.price_amount is not None]
        prices = [Decimal(m.price_amount) for m in priced]
        per_m2 = [Decimal(m.price_amount) / Decimal(m.area_m2) for m in priced if m.area_m2]
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
            dates = [m.published_at.date() for m in priced if m.published_at]
            observed(
                "prices",
                "observed.segment_median",
                sample=len(prices),
                source="listings",
                method="median_quartiles_of_current_asking_prices",
                period=(min(dates) if dates else today, today),
                has_demo=any(m.is_demo for m in priced),
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
                metric="segment_medians", reason="sample_too_small", detail={"minimum": MIN_SAMPLE}
            )
        )

    # --- Initial asking price per m², by publication month (one segment).
    # Uses each listing's FIRST recorded asking price (the price when it was
    # published), across every listing published in the scope — not today's price
    # of the survivors — so a month's value is what was asked in that month.
    trend_done = False
    if groups:
        (code, purpose, currency), _ = max(groups.items(), key=lambda kv: len(kv[1]))
        cohort = db.execute(
            select(
                Property.id,
                Property.published_at,
                Property.area_m2,
                Property.is_demo,
            ).where(
                *base,
                Property.published_at.is_not(None),
                Property.status.notin_(NEVER_PUBLIC),
                Property.property_type_code == code,
                Property.purpose == purpose,
            )
        ).all()
        first_price: dict[uuid.UUID, tuple[Decimal, str]] = {}
        if cohort:
            for pid, amount, cur in db.execute(
                select(
                    PropertyPriceHistory.property_id,
                    PropertyPriceHistory.price_amount,
                    PropertyPriceHistory.currency,
                )
                .where(
                    PropertyPriceHistory.property_id.in_([c.id for c in cohort]),
                    PropertyPriceHistory.price_amount.is_not(None),
                )
                .order_by(PropertyPriceHistory.property_id, PropertyPriceHistory.changed_at)
            ).all():
                first_price.setdefault(pid, (Decimal(amount), cur))
        months: dict[str, list[Decimal]] = {}
        month_demo: dict[str, bool] = {}
        for c in cohort:
            initial = first_price.get(c.id)
            if initial is None or initial[1] != currency or not c.area_m2:
                continue  # no recorded initial price, other currency, or no area
            key = c.published_at.strftime("%Y-%m")
            months.setdefault(key, []).append(initial[0] / Decimal(c.area_m2))
            month_demo[key] = month_demo.get(key, False) or bool(c.is_demo)
        usable = {k: v for k, v in sorted(months.items()) if len(v) >= MIN_MONTH_SAMPLE}
        if len(usable) >= 2:
            first_k, last_k = next(iter(usable)), list(usable)[-1]
            first_v = Decimal(statistics.median(usable[first_k]))
            last_v = Decimal(statistics.median(usable[last_k]))
            if first_v:
                change = float((last_v - first_v) / first_v * 100)
                y, m = (int(x) for x in last_k.split("-"))
                end = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)).isoformat()
                observed(
                    "dynamics",
                    "observed.initial_price_per_m2_change",
                    sample=sum(len(v) for v in usable.values()),
                    source="price_history",
                    method="median_initial_asking_price_per_m2_by_publication_month",
                    period=(
                        date.fromisoformat(f"{first_k}-01"),
                        min(date.fromisoformat(end), today),
                    ),
                    has_demo=any(month_demo[k] for k in usable),
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

    # --- Asking-price changes on current listings (same currency only)
    ids = [r.id for r in rows]
    demo_ids = {r.id for r in rows if r.is_demo}
    if ids:
        hist = db.execute(
            select(
                PropertyPriceHistory.property_id,
                PropertyPriceHistory.price_amount,
                PropertyPriceHistory.currency,
                PropertyPriceHistory.changed_at,
            )
            .where(
                PropertyPriceHistory.property_id.in_(ids),
                PropertyPriceHistory.price_amount.is_not(None),
            )
            .order_by(PropertyPriceHistory.property_id, PropertyPriceHistory.changed_at)
        ).all()
        series: dict[uuid.UUID, list[tuple[Decimal, str, datetime]]] = {}
        for pid, amount, cur, at in hist:
            series.setdefault(pid, []).append((Decimal(amount), cur, at))
        changes: list[float] = []
        changed_ids: list[uuid.UUID] = []
        stamps: list[datetime] = []
        for pid, v in series.items():
            first, last = v[0], v[-1]
            # a change is only measured when both prices are in the same currency
            if len(v) > 1 and first[1] == last[1] and first[0] and first[0] != last[0]:
                changes.append(float((last[0] - first[0]) / first[0] * 100))
                changed_ids.append(pid)
                stamps += [first[2], last[2]]
        period = (min(stamps).date(), max(stamps).date()) if stamps else (None, today)
        fact(
            "dynamics",
            "fact.listings_with_price_change",
            source="price_history",
            period=period,
            has_demo=any(i in demo_ids for i in changed_ids),
            count=len(changes),
            of=n,
        )
        if len(changes) >= MIN_SAMPLE:
            observed(
                "dynamics",
                "observed.median_price_change",
                sample=len(changes),
                source="price_history",
                method="median_change_first_to_latest_asking_price_same_currency",
                period=period,
                has_demo=any(i in demo_ids for i in changed_ids),
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

    # --- Days until the lister marked a listing sold/rented (lister-reported,
    # not a verified transaction; withdrawn/expired listings are not counted)
    closed_rows = db.execute(
        select(
            Property.id,
            Property.published_at,
            Property.is_demo,
            func.max(PropertyStatusHistory.changed_at),
        )
        .join(PropertyStatusHistory, PropertyStatusHistory.property_id == Property.id)
        .where(
            *base,
            Property.published_at.is_not(None),
            Property.status.in_(MARKED_CLOSED),
            PropertyStatusHistory.to_status.in_(MARKED_CLOSED),
        )
        .group_by(Property.id, Property.published_at, Property.is_demo)
    ).all()
    closed = [
        (published, at, is_demo)
        for _, published, is_demo, at in closed_rows
        if at and published and at >= published
    ]
    if len(closed) >= MIN_SAMPLE:
        observed(
            "dynamics",
            "observed.median_days_to_marked_closed",
            sample=len(closed),
            source="status_history",
            method="median_days_published_to_marked_sold_or_rented",
            period=(min(c[0] for c in closed).date(), max(c[1] for c in closed).date()),
            has_demo=any(c[2] for c in closed),
            days=int(statistics.median((at - published).days for published, at, _ in closed)),
        )
    else:
        unavailable.append(
            Unavailable(
                metric="time_on_market",
                reason="too_few_closed_listings",
                detail={"closed_listings": len(closed), "minimum": MIN_SAMPLE},
            )
        )
    active_ages = [(now - r.published_at).days for r in rows if r.published_at]
    if len(active_ages) >= MIN_SAMPLE:
        observed(
            "dynamics",
            "observed.median_active_age",
            sample=len(active_ages),
            source="listings",
            method="median_days_since_publication",
            period=(oldest, today),
            days=int(statistics.median(active_ages)),
        )

    # --- Interest on MAKAN (facts over a fixed window; not market demand)
    since = now - timedelta(days=DEMAND_WINDOW_DAYS)
    if ids:
        from app.analytics.models import PropertyViewDaily

        inquiries = db.execute(
            select(func.count()).where(Inquiry.property_id.in_(ids), Inquiry.created_at >= since)
        ).scalar_one()
        favorites = db.execute(
            select(func.count()).where(Favorite.property_id.in_(ids), Favorite.created_at >= since)
        ).scalar_one()
        views = db.execute(
            select(func.coalesce(func.sum(PropertyViewDaily.views), 0)).where(
                PropertyViewDaily.property_id.in_(ids),
                PropertyViewDaily.day >= since.date(),
            )
        ).scalar_one()
        fact(
            "demand",
            "fact.demand_30d",
            source="interest",
            period=(since.date(), today),
            views=int(views),
            inquiries=int(inquiries),
            favorites=int(favorites),
            days=DEMAND_WINDOW_DAYS,
        )

    # --- Supply over time: only recorded daily snapshots (never back-filled,
    # never inferred for districts)
    history: list[SupplyPoint] = []
    if scope["level"] == "district":
        unavailable.append(Unavailable(metric="supply_trend", reason="not_recorded_for_districts"))
    else:
        scope_key = "iraq" if scope["level"] == "iraq" else f"{scope['level']}:{scope['id']}"
        snap_rows = db.execute(
            select(
                MarketSnapshot.day,
                func.sum(MarketSnapshot.active_listings),
                func.sum(MarketSnapshot.demo_listings),
            )
            .where(
                MarketSnapshot.scope_key == scope_key,
                MarketSnapshot.include_demo.is_(include_demo),
            )
            .group_by(MarketSnapshot.day)
            .order_by(MarketSnapshot.day)
        ).all()
        history = [SupplyPoint(day=d, active_listings=int(total)) for d, total, _ in snap_rows]
        if len(history) >= 2:
            fact(
                "supply",
                "fact.supply_change",
                source="snapshots",
                method="recorded_daily_snapshots",
                period=(history[0].day, history[-1].day),
                has_demo=any(int(d or 0) for _, _, d in snap_rows),
                days_recorded=len(history),
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

    # --- Possible duplicates: a heuristic match, never a confirmed duplicate
    if ids and n <= DUPLICATE_SCAN_LIMIT:
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
        fact(
            "quality",
            "fact.possible_duplicate_pairs",
            method="heuristic_same_type_price_currency_area_2pct_within_200m",
            pairs=int(pairs),
        )
    elif ids:
        unavailable.append(
            Unavailable(
                metric="possible_duplicates",
                reason="scope_too_large",
                detail={"listings": n, "limit": DUPLICATE_SCAN_LIMIT},
            )
        )

    # --- Area comparison: ONE segment (most common sale type, its main currency)
    areas: list[AreaRow] = []
    areas_basis: AreaBasis | None = None
    if child_level:
        model = District if child_level == "district" else City
        column = Property.district_id if child_level == "district" else Property.city_id
        counts: dict[uuid.UUID, int] = {
            area_id: total
            for area_id, total in db.execute(
                select(column, func.count()).where(*active, column.is_not(None)).group_by(column)
            ).all()
            if area_id is not None  # excluded by the query; narrows the type
        }
        sale = [k for k in groups if k[1] == "SALE"]
        if sale:
            code, purpose, currency = max(sale, key=lambda k: len(groups[k]))
            t = types.get(code)
            areas_basis = AreaBasis(
                property_type_code=code,
                type_ar=t.name_ar if t else code,
                type_en=t.name_en if t else code,
                purpose=purpose,
                currency=currency,
            )
        values_by_area: dict[uuid.UUID, list[Decimal]] = {}
        area_demo: dict[uuid.UUID, bool] = {}
        if areas_basis:
            for area_id, price, m2, is_demo in db.execute(
                select(column, Property.price_amount, Property.area_m2, Property.is_demo).where(
                    *active,
                    column.is_not(None),
                    Property.property_type_code == areas_basis.property_type_code,
                    Property.purpose == areas_basis.purpose,
                    Property.currency == areas_basis.currency,
                    Property.price_on_request.is_(False),
                    Property.price_amount.is_not(None),
                )
            ).all():
                if m2:
                    values_by_area.setdefault(area_id, []).append(Decimal(price) / Decimal(m2))
                    area_demo[area_id] = area_demo.get(area_id, False) or bool(is_demo)
        places = {
            p.id: p for p in db.execute(select(model).where(model.id.in_(list(counts)))).scalars()
        }
        for area_id, count in sorted(counts.items(), key=lambda kv: -kv[1])[:30]:
            place = places.get(area_id)
            if place is None:
                continue
            values = values_by_area.get(area_id, [])
            median = _q(statistics.median(values)) if len(values) >= MIN_SAMPLE else None
            areas.append(
                AreaRow(
                    level=child_level,
                    id=area_id,
                    name_ar=place.name_ar,
                    name_en=place.name_en,
                    active_listings=int(count),
                    median_price_per_m2=median,
                    currency=areas_basis.currency if median and areas_basis else None,
                    sample=len(values),
                )
            )
        if areas:
            fact("areas", "fact.area_breakdown", level=child_level, areas=len(areas))

    # --- Provenance and confidence
    confidence, reasons = _confidence(n, demo_n, newest_at, now)
    provenance = Provenance(
        source="MAKAN platform listings (asking prices, not transaction prices)",
        coverage=f"{scope['level']}: {scope['name_en'] or scope['name_ar']}",
        observation_from=oldest,
        observation_to=newest_at.date() if newest_at else None,
        sample_listings=n,
        includes_demo=demo,
        demo_share=round(demo_n / n, 3) if n else 0.0,
        methodology=[
            f"no statistic with fewer than {MIN_SAMPLE} observations",
            "currencies are never converted or mixed",
            "asking prices only; MAKAN collects no transaction prices",
            "price trend: median initial asking price per m² by publication month, one "
            f"segment, months with {MIN_MONTH_SAMPLE}+ listings",
            "sold/rented timing is lister-reported, not verified",
            "interest is views, saves and inquiries on MAKAN, not market demand",
            "supply over time comes from daily snapshots recorded going forward, never back-filled",
            "possible duplicates are a heuristic match, not confirmed duplicates",
        ],
        confidence=confidence,
        confidence_reasons=reasons,
        last_update=now,
        newest_listing=newest_at.date() if newest_at else None,
    )

    # --- AI interpretation: wording only, from the facts above, guarded
    provider: str | None = None
    reported = [s for s in statements if s.kind == "OBSERVED"]
    if interpret and reported:
        facts: dict[str, Any] = {
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
            data, generation = ai_service.generate(
                db,
                principal,
                feature="market.interpretation",
                task="market.interpretation",
                system=(
                    "You restate Iraqi property listing data in plain words. Use only the facts "
                    "given; add no numbers, places or claims of your own. Begin with 'Based on "
                    "the available data'. These are asking prices from listings, never sale or "
                    "transaction prices. Never forecast, never advise, never promise returns. "
                    "If includes_demo is true, say the figures include demonstration data."
                ),
                instructions="At most three short sentences.",
                facts=facts,
                output_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
                validate=_ai_check,
                language=language,
            )
        except AppError as exc:
            if exc.code != "AI_QUOTA_EXCEEDED":
                raise
            unavailable.append(Unavailable(metric="ai_interpretation", reason="ai_quota_reached"))
        else:
            provider = generation.provider
            statements.append(
                MarketStatement(
                    kind="AI_INTERPRETATION",
                    origin="ai",
                    section="interpretation",
                    key="ai.text",
                    text=str(data["text"])[:600],
                    demo=demo,
                    source="ai",
                    method="restatement_of_observed_statistics",
                    period_from=oldest,
                    period_to=today,
                )
            )

    return MarketReport(
        scope=scope,
        provenance=provenance,
        statements=statements,
        segments=segments,
        areas=areas,
        areas_basis=areas_basis,
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
