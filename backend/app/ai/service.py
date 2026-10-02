"""AI features.

Two families:

* **Generative** (descriptions, titles, Arabic improvement, summaries, lead
  replies/summaries, natural-language search): go through the configured
  ``AIProvider``; outputs are schema-checked and fact-guarded, and fall back to
  the deterministic template when a provider fails or invents facts.
* **Analytical** (price and investment estimates, scoring, neighbourhood
  facts, listing quality, duplicates, risk signals, similar listings,
  recommendations, lead priority): computed from platform data with stated
  methodology, sample sizes and limitations. Estimates are labelled as
  estimates and are never presented as market facts.

Every call is recorded in ``ai_generations`` for traceability and usage.
"""

from __future__ import annotations

import re
import statistics
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import cast, func, or_, select
from sqlalchemy.orm import Session

from app.ai import guards
from app.ai.models import AIGeneration
from app.ai.providers import AIProviderError, AIRequest, MockAIProvider, get_provider
from app.ai.schemas import AIEnvelope, ResultKind
from app.auth.deps import Principal
from app.core.config import get_settings
from app.core.errors import AppError
from app.crm.models import ActivityKind, Lead, LeadActivity, LeadStatus
from app.geo.models import City, District, Neighborhood
from app.properties.models import Amenity, Property, PropertyMedia, PropertyType
from app.users.models import User

PURPOSES = {
    "SALE": ("للبيع", "for sale"),
    "RENT": ("للإيجار", "for rent"),
    "LEASE": ("للتأجير طويل الأمد", "for long-term lease"),
    "RAHN": ("للرهن", "for rahn"),
    "MUSATAHA": ("للمساطحة", "for musataha"),
    "EXCHANGE": ("للمبادلة", "for exchange"),
}
CONDITIONS = {
    "NEW": ("جديد", "new"),
    "EXCELLENT": ("ممتاز", "excellent"),
    "GOOD": ("جيد", "good"),
    "NEEDS_RENOVATION": ("يحتاج ترميم", "needs renovation"),
    "UNDER_CONSTRUCTION": ("قيد الإنشاء", "under construction"),
}
FURNISHING = {
    "UNFURNISHED": ("غير مفروش", "unfurnished"),
    "SEMI_FURNISHED": ("نصف مفروش", "semi-furnished"),
    "FURNISHED": ("مفروش", "furnished"),
}
OWNERSHIP = {
    "TAPU": "طابو صرف",
    "AGRICULTURAL": "زراعي",
    "HUJJA": "حجة",
    "INVESTMENT": "سند استثمار",
    "MUSATAHA": "عقد مساطحة",
    "SHARED": "مشاع",
    "OTHER": "أخرى",
}

ASKING_PRICE_LIMITATION = (
    "Based on asking prices of listings on this platform, not on completed transactions."
)
MIN_COMPARABLES = 3
COMPARABLE_RADIUS_M = 3000


def _now() -> datetime:
    return datetime.now(UTC)


def _num(value: Decimal | None) -> str | None:
    if value is None:
        return None
    text = f"{value.normalize():f}"
    return text


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q0(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


# --- recording


def _record(
    db: Session,
    *,
    feature: str,
    kind: str,
    provider: str,
    model: str,
    status: str,
    principal: Principal | None,
    output: dict[str, Any] | None,
    property_id: uuid.UUID | None = None,
    lead_id: uuid.UUID | None = None,
    input_summary: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    confidence: float | None = None,
    latency_ms: int = 0,
    tokens: tuple[int | None, int | None] = (None, None),
) -> AIGeneration:
    row = AIGeneration(
        feature=feature,
        kind=kind,
        provider=provider,
        model=model,
        status=status,
        user_id=principal.id if principal else None,
        property_id=property_id,
        lead_id=lead_id,
        input_summary=input_summary,
        output=output,
        validation_errors=errors or None,
        confidence=confidence,
        latency_ms=latency_ms,
        input_tokens=tokens[0],
        output_tokens=tokens[1],
    )
    db.add(row)
    db.flush()
    return row


def _envelope(
    row: AIGeneration,
    *,
    kind: ResultKind,
    methodology: str,
    result: dict[str, Any],
    confidence: float | None = None,
    sources: list[str] | None = None,
    limitations: list[str] | None = None,
    disclaimer: str | None = None,
) -> AIEnvelope:
    return AIEnvelope(
        feature=row.feature,
        kind=kind,
        provider=row.provider,
        model=row.model,
        generation_id=row.id,
        confidence=confidence,
        methodology=methodology,
        data_sources=sources or [],
        limitations=limitations or [],
        disclaimer=disclaimer,
        created_at=row.created_at or _now(),
        result=result,
    )


def _analysis(
    db: Session,
    principal: Principal | None,
    *,
    feature: str,
    kind: ResultKind,
    methodology: str,
    result: dict[str, Any],
    property_id: uuid.UUID | None = None,
    lead_id: uuid.UUID | None = None,
    confidence: float | None = None,
    sources: list[str] | None = None,
    limitations: list[str] | None = None,
    disclaimer: str | None = None,
) -> AIEnvelope:
    row = _record(
        db,
        feature=feature,
        kind=kind,
        provider="platform",
        model="statistics-v1",
        status="SUCCEEDED",
        principal=principal,
        output=result,
        property_id=property_id,
        lead_id=lead_id,
        confidence=confidence,
    )
    db.commit()
    return _envelope(
        row,
        kind=kind,
        methodology=methodology,
        result=result,
        confidence=confidence,
        sources=sources,
        limitations=limitations,
        disclaimer=disclaimer,
    )


# --- generation pipeline


def _check_quota(db: Session, principal: Principal | None) -> None:
    limit = get_settings().ai_daily_limit_per_user
    if principal is None or limit == 0:
        return
    used = db.execute(
        select(func.count()).where(
            AIGeneration.user_id == principal.id,
            AIGeneration.kind == "generated",
            AIGeneration.created_at >= _now() - timedelta(days=1),
        )
    ).scalar_one()
    if used >= limit:
        raise AppError(
            "Daily AI limit reached. Try again later.",
            code="AI_QUOTA_EXCEEDED",
            status_code=429,
        )


def generate(
    db: Session,
    principal: Principal | None,
    *,
    feature: str,
    task: str,
    system: str,
    instructions: str,
    facts: dict[str, Any],
    output_schema: dict[str, Any],
    validate: Callable[[dict[str, Any]], list[str]],
    language: str = "ar",
    property_id: uuid.UUID | None = None,
    lead_id: uuid.UUID | None = None,
    guard_text: bool = True,
    kind: ResultKind = "generated",
) -> tuple[dict[str, Any], AIGeneration]:
    """Run a generative task with schema validation, fact guards and fallback."""
    _check_quota(db, principal)
    provider = get_provider()
    request = AIRequest(
        task=task,
        system=system,
        facts=facts,
        output_schema=output_schema,
        instructions=instructions,
        language=language,
        max_tokens=get_settings().ai_max_output_tokens,
    )
    summary = {"task": task, "language": language, "fact_keys": sorted(facts)}
    status, errors = "SUCCEEDED", []
    try:
        response = provider.generate(request)
        data = response.data
        errors = validate(data)
        if guard_text and not errors:
            errors = guards.check_text(guards.collect_text(data), facts)
        if errors:
            status = "REJECTED"
    except AIProviderError as exc:
        status, errors = "FAILED", [str(exc)]
        response = None
    if status != "SUCCEEDED":
        # Deterministic, fact-only fallback; the original failure stays visible in the record.
        data = MockAIProvider().generate(request).data
        row = _record(
            db,
            feature=feature,
            kind=kind,
            provider="mock",
            model=MockAIProvider.model,
            status="FALLBACK",
            principal=principal,
            output=data,
            property_id=property_id,
            lead_id=lead_id,
            input_summary=summary,
            errors=[f"{provider.name}:{status}:{e}" for e in errors],
        )
    else:
        assert response is not None  # noqa: S101
        row = _record(
            db,
            feature=feature,
            kind=kind,
            provider=response.provider,
            model=response.model,
            status="SUCCEEDED",
            principal=principal,
            output=data,
            property_id=property_id,
            lead_id=lead_id,
            input_summary=summary,
            latency_ms=response.latency_ms,
            tokens=(response.input_tokens, response.output_tokens),
        )
    db.commit()
    return data, row


def _require_str_fields(*names: str) -> Callable[[dict[str, Any]], list[str]]:
    def check(data: dict[str, Any]) -> list[str]:
        return [f"missing_or_invalid:{n}" for n in names if not isinstance(data.get(n), str)]

    return check


# --- facts


def property_facts(db: Session, prop: Property) -> dict[str, Any]:
    """Only what the lister declared (plus reference-data labels)."""
    ptype = db.get(PropertyType, prop.property_type_code)
    names = (
        {
            a.code: a
            for a in db.execute(
                select(Amenity).where(
                    Amenity.code.in_([link.amenity_code for link in prop.amenity_links])
                )
            ).scalars()
        }
        if prop.amenity_links
        else {}
    )
    city = db.get(City, prop.city_id)
    district = db.get(District, prop.district_id) if prop.district_id else None
    neighborhood = db.get(Neighborhood, prop.neighborhood_id) if prop.neighborhood_id else None
    facts: dict[str, Any] = {
        "type_ar": ptype.name_ar if ptype else prop.property_type_code,
        "type_en": ptype.name_en if ptype else prop.property_type_code,
        "purpose_ar": PURPOSES.get(prop.purpose, ("", ""))[0],
        "purpose_en": PURPOSES.get(prop.purpose, ("", ""))[1],
        "city_ar": city.name_ar if city else None,
        "city_en": city.name_en if city else None,
        "district_ar": district.name_ar if district else None,
        "district_en": district.name_en if district else None,
        "neighborhood_ar": neighborhood.name_ar if neighborhood else None,
        "neighborhood_en": neighborhood.name_en if neighborhood else None,
        "area_m2": _num(prop.area_m2),
        "land_area_m2": _num(prop.land_area_m2),
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "floors": prop.floors,
        "year_built": prop.year_built,
        "condition_ar": CONDITIONS.get(prop.condition or "", (None, None))[0],
        "condition_en": CONDITIONS.get(prop.condition or "", (None, None))[1],
        "furnishing_ar": FURNISHING.get(prop.furnishing or "", (None, None))[0],
        "furnishing_en": FURNISHING.get(prop.furnishing or "", (None, None))[1],
        "amenities_ar": [names[c].name_ar for c in sorted(names)],
        "amenities_en": [names[c].name_en for c in sorted(names)],
        "verified": prop.verified_at is not None,
        "ownership_declared": OWNERSHIP.get(prop.ownership_document)
        if prop.ownership_document != "UNKNOWN"
        else None,
    }
    if not prop.price_on_request and prop.price_amount is not None:
        facts["price_text"] = f"{_q0(prop.price_amount):,} {prop.currency}"
        if prop.rent_period:
            facts["rent_period"] = prop.rent_period
    return {k: v for k, v in facts.items() if v not in (None, "", [])}


LISTING_SYSTEM = (
    "You write Iraqi real-estate listing copy. Use ONLY the facts provided. Never add or "
    "guess prices, areas, rooms, ownership or legal status, amenities, features, location "
    "details or availability. If a fact is missing, do not mention it. Arabic must be natural "
    "Modern Standard Arabic suitable for Iraq."
)


def describe_listing(
    db: Session, principal: Principal, prop: Property, language: str
) -> AIEnvelope:
    facts = property_facts(db, prop)
    data, row = generate(
        db,
        principal,
        feature="listing.description",
        task="listing.description",
        system=LISTING_SYSTEM,
        instructions="Write a property description and up to 6 short highlights.",
        facts=facts,
        output_schema={
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "highlights": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["description"],
        },
        validate=_require_str_fields("description"),
        language=language,
        property_id=prop.id,
    )
    return _envelope(
        row,
        kind="generated",
        methodology="Text generated only from the listing's declared fields; numbers and "
        "sensitive claims are checked against those fields.",
        result={"description": data["description"], "highlights": data.get("highlights", [])},
        sources=["listing fields"],
        limitations=["Draft only — review before publishing; it is not saved automatically."],
    )


def title_listing(db: Session, principal: Principal, prop: Property, language: str) -> AIEnvelope:
    facts = property_facts(db, prop)

    def check(data: dict[str, Any]) -> list[str]:
        titles = data.get("titles")
        ok = isinstance(titles, list) and titles and all(isinstance(t, str) for t in titles)
        return [] if ok else ["missing_or_invalid:titles"]

    data, row = generate(
        db,
        principal,
        feature="listing.title",
        task="listing.title",
        system=LISTING_SYSTEM,
        instructions="Suggest up to 3 short listing titles (max 120 characters each).",
        facts=facts,
        output_schema={
            "type": "object",
            "properties": {"titles": {"type": "array", "items": {"type": "string"}}},
            "required": ["titles"],
        },
        validate=check,
        language=language,
        property_id=prop.id,
    )
    titles = [t[:120] for t in data["titles"][:3]]
    return _envelope(
        row,
        kind="generated",
        methodology="Titles composed only from the listing's declared fields.",
        result={"titles": titles},
        sources=["listing fields"],
        limitations=["Suggestions only — not saved automatically."],
    )


def improve_arabic(db: Session, principal: Principal, text: str) -> AIEnvelope:
    facts = {"text": text}

    def check(data: dict[str, Any]) -> list[str]:
        errors = _require_str_fields("text")(data)
        if not errors and guards._numbers(data["text"]) != guards._numbers(text):
            errors.append("numbers_changed")
        return errors

    data, row = generate(
        db,
        principal,
        feature="text.improve_ar",
        task="text.improve_ar",
        system="You edit Arabic real-estate text for clarity, grammar and punctuation without "
        "changing its meaning. Keep every number, name and claim exactly as written; add "
        "nothing.",
        instructions="Improve the Arabic text in FACTS.text.",
        facts=facts,
        output_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}, "changes": {"type": "array"}},
            "required": ["text"],
        },
        validate=check,
        guard_text=False,  # numbers are checked for exact preservation instead
    )
    return _envelope(
        row,
        kind="generated",
        methodology="Language clean-up with numbers preserved exactly.",
        result={"text": data["text"], "changes": data.get("changes", [])},
        limitations=["Meaning is preserved; facts are not checked for truth."],
    )


def summarize_property(
    db: Session, principal: Principal | None, prop: Property, language: str
) -> AIEnvelope:
    facts = property_facts(db, prop)

    def check(data: dict[str, Any]) -> list[str]:
        return _require_str_fields("summary")(data)

    data, row = generate(
        db,
        principal,
        feature="property.summary",
        task="property.summary",
        system=LISTING_SYSTEM,
        instructions="Summarize the listing in one sentence plus short bullet points.",
        facts=facts,
        output_schema={
            "type": "object",
            "properties": {"summary": {"type": "string"}, "bullets": {"type": "array"}},
            "required": ["summary"],
        },
        validate=check,
        language=language,
        property_id=prop.id,
    )
    return _envelope(
        row,
        kind="generated",
        methodology="Summary of the listing's declared fields only.",
        result={"summary": data["summary"], "bullets": data.get("bullets", [])},
        sources=["listing fields"],
    )


# --- comparables


def _geog(col: Any) -> Any:
    return cast(col, Geography(geometry_type="POINT", srid=4326))


def comparables(
    db: Session,
    prop: Property,
    *,
    purpose: str | None = None,
    rent_period: str | None = None,
    limit: int = 200,
) -> tuple[list[Property], str]:
    """Public, priced listings like ``prop`` nearby (or in the same district/city)."""
    purpose = purpose or prop.purpose
    stmt = select(Property).where(
        Property.id != prop.id,
        Property.status == "APPROVED",
        Property.deleted_at.is_(None),
        Property.property_type_code == prop.property_type_code,
        Property.purpose == purpose,
        Property.currency == prop.currency,
        Property.price_on_request.is_(False),
        Property.price_amount.is_not(None),
        Property.area_m2 > 0,
    )
    if rent_period is not None or purpose in ("RENT", "LEASE"):
        stmt = stmt.where(Property.rent_period == (rent_period or prop.rent_period))
    if not prop.is_demo:
        stmt = stmt.where(Property.is_demo.is_(False))  # demo data never informs real estimates
    if prop.display_location is not None:
        centre = _geog(
            select(Property.display_location).where(Property.id == prop.id).scalar_subquery()
        )
        scoped = stmt.where(
            Property.display_location.is_not(None),
            func.ST_DWithin(_geog(Property.display_location), centre, COMPARABLE_RADIUS_M),
        )
        rows = list(db.execute(scoped.limit(limit)).scalars())
        if len(rows) >= MIN_COMPARABLES:
            return rows, f"within {COMPARABLE_RADIUS_M // 1000} km"
    if prop.district_id:
        rows = list(
            db.execute(stmt.where(Property.district_id == prop.district_id).limit(limit)).scalars()
        )
        if len(rows) >= MIN_COMPARABLES:
            return rows, "same district"
    rows = list(db.execute(stmt.where(Property.city_id == prop.city_id).limit(limit)).scalars())
    return rows, "same city"


def _per_m2(props: list[Property]) -> list[Decimal]:
    out = []
    for p in props:
        if p.price_amount is not None and p.area_m2:
            out.append(Decimal(p.price_amount) / Decimal(p.area_m2))
    return out


def _quartiles(values: list[Decimal]) -> tuple[Decimal, Decimal, Decimal]:
    ordered = sorted(values)
    if len(ordered) < 4:
        return ordered[0], Decimal(statistics.median(ordered)), ordered[-1]
    q = statistics.quantiles(ordered, n=4, method="inclusive")
    return Decimal(q[0]), Decimal(q[1]), Decimal(q[2])


def price_analysis(db: Session, principal: Principal | None, prop: Property) -> AIEnvelope:
    limitations = [
        ASKING_PRICE_LIMITATION,
        "No adjustment for condition, finishing, floor, view or legal status.",
        "Small samples make estimates unreliable.",
    ]
    comps, scope = comparables(db, prop)
    per_m2 = _per_m2(comps)
    result: dict[str, Any] = {
        "currency": prop.currency,
        "comparable_count": len(per_m2),
        "comparable_scope": scope,
        "comparable_ids": [str(p.id) for p in comps[:10]],
        "value": None,
        "low": None,
        "high": None,
        "price_per_m2_median": None,
        "asking_price_position": None,
        "is_estimate": True,
    }
    confidence: float | None = None
    if not prop.area_m2:
        result["unavailable_reason"] = "listing_has_no_area"
    elif len(per_m2) < MIN_COMPARABLES:
        result["unavailable_reason"] = "insufficient_comparables"
    else:
        low, mid, high = _quartiles(per_m2)
        area = Decimal(prop.area_m2)
        result.update(
            value=str(_q0(mid * area)),
            low=str(_q0(low * area)),
            high=str(_q0(high * area)),
            price_per_m2_median=str(_q2(mid)),
        )
        if prop.price_amount is not None and not prop.price_on_request:
            asking = Decimal(prop.price_amount)
            result["asking_price_position"] = (
                "below_range"
                if asking < low * area
                else "above_range"
                if asking > high * area
                else "within_range"
            )
        spread = float((high - low) / mid) if mid else 1.0
        confidence = round(max(0.05, min(0.9, (len(per_m2) / 20) * (1 - min(spread, 0.9)))), 2)
    return _analysis(
        db,
        principal,
        feature="price.analysis",
        kind="estimate",
        methodology=(
            "Median and interquartile range of asking price per m² of comparable public listings "
            "(same type, purpose and currency; nearest scope with at least 3 listings), "
            "multiplied by this listing's area. Currencies are never converted."
        ),
        result=result,
        property_id=prop.id,
        confidence=confidence,
        sources=["public listings on this platform"],
        limitations=limitations,
        disclaimer="Estimate — not a valuation and not a verified market price.",
    )


def compare_properties(
    db: Session, principal: Principal | None, props: list[Property]
) -> AIEnvelope:
    """Side-by-side figures from declared facts plus each listing's local median.

    Prices are compared only between listings with the same currency and
    purpose (never converted); "highlights" name the listing with the lowest
    price per m², the largest area and the most bedrooms.
    """
    rows: list[dict[str, Any]] = []
    for prop in props:
        per_m2: Decimal | None = None
        if prop.price_amount is not None and not prop.price_on_request and prop.area_m2:
            per_m2 = _q2(Decimal(prop.price_amount) / Decimal(prop.area_m2))
        comps, scope = comparables(db, prop)
        values = _per_m2(comps)
        median = _quartiles(values)[1] if len(values) >= MIN_COMPARABLES else None
        vs_median = (
            float(_q2((per_m2 - median) / median * 100)) if per_m2 is not None and median else None
        )
        rows.append(
            {
                "id": str(prop.id),
                "currency": prop.currency,
                "purpose": prop.purpose,
                "price_per_m2": str(per_m2) if per_m2 is not None else None,
                "local_median_per_m2": str(_q2(median)) if median else None,
                "median_scope": scope if median else None,
                "vs_local_median_percent": vs_median,
                "area_m2": str(prop.area_m2) if prop.area_m2 is not None else None,
                "bedrooms": prop.bedrooms,
            }
        )
    priced = [r for r in rows if r["price_per_m2"] is not None]
    comparable = len({(r["currency"], r["purpose"]) for r in priced}) == 1 and len(priced) >= 2
    with_area = [r for r in rows if r["area_m2"]]
    with_rooms = [r for r in rows if r["bedrooms"] is not None]
    highlights: dict[str, str | None] = {
        "lowest_price_per_m2": (
            min(priced, key=lambda r: Decimal(r["price_per_m2"]))["id"] if comparable else None
        ),
        "largest_area": (
            max(with_area, key=lambda r: Decimal(r["area_m2"]))["id"] if with_area else None
        ),
        "most_bedrooms": (
            max(with_rooms, key=lambda r: int(r["bedrooms"]))["id"] if with_rooms else None
        ),
    }
    limitations = ["Asking prices, not transaction prices."]
    if not comparable:
        limitations.append("Prices are not compared: different currency or purpose.")
    return _analysis(
        db,
        principal,
        feature="property.compare",
        kind="analysis",
        methodology=(
            "Price per m² from each listing's declared price and area, compared with the median "
            "price per m² of similar public listings (same type, purpose and currency). "
            "Prices are compared only when currency and purpose match; no conversion."
        ),
        result={"properties": rows, "prices_comparable": comparable, "highlights": highlights},
        sources=["listing fields", "public listings on this platform"],
        limitations=limitations,
    )


def investment_analysis(db: Session, principal: Principal | None, prop: Property) -> AIEnvelope:
    result: dict[str, Any] = {
        "currency": prop.currency,
        "gross_yield_percent": None,
        "estimated_monthly_rent": None,
        "rent_comparable_count": 0,
        "is_estimate": True,
    }
    confidence = None
    if prop.purpose != "SALE":
        result["unavailable_reason"] = "only_for_sale_listings"
    elif prop.price_on_request or prop.price_amount is None or not prop.area_m2:
        result["unavailable_reason"] = "price_or_area_missing"
    else:
        rents, scope = comparables(db, prop, purpose="RENT", rent_period="MONTHLY")
        per_m2 = _per_m2(rents)
        result["rent_comparable_count"] = len(per_m2)
        result["rent_comparable_scope"] = scope
        if len(per_m2) < MIN_COMPARABLES:
            result["unavailable_reason"] = "insufficient_rental_comparables"
        else:
            monthly = Decimal(statistics.median(per_m2)) * Decimal(prop.area_m2)
            yearly = monthly * 12
            result["estimated_monthly_rent"] = str(_q0(monthly))
            result["gross_yield_percent"] = str(_q2(yearly / Decimal(prop.price_amount) * 100))
            confidence = round(min(0.8, len(per_m2) / 25), 2)
    return _analysis(
        db,
        principal,
        feature="investment.analysis",
        kind="estimate",
        methodology=(
            "Gross yield = (median monthly asking rent per m² of comparable rental listings × area "
            "× 12) ÷ asking price. Same type and currency only."
        ),
        result=result,
        property_id=prop.id,
        confidence=confidence,
        sources=["public listings on this platform"],
        limitations=[
            ASKING_PRICE_LIMITATION,
            "Gross figure: excludes vacancy, maintenance, fees and taxes.",
            "Not financial advice; returns are not guaranteed.",
        ],
        disclaimer="Estimate — not financial advice.",
    )


# --- quality, duplicates, risk

QUALITY_CHECKS = [
    ("title_length", 10),
    ("description_length", 15),
    ("photos", 20),
    ("location", 15),
    ("area", 10),
    ("rooms", 10),
    ("price", 10),
    ("amenities", 5),
    ("english", 5),
]
RESIDENTIAL = {"APARTMENT", "HOUSE", "VILLA"}


def quality_report(prop: Property) -> dict[str, Any]:
    photos = [m for m in prop.media if m.kind == "IMAGE" and m.moderation == "APPROVED"]
    passed = {
        "title_length": len(prop.title_ar.strip()) >= 12,
        "description_length": len((prop.description_ar or "").strip()) >= 80,
        "photos": len(photos) >= 3,
        "location": prop.location is not None,
        "area": bool(prop.area_m2),
        "rooms": prop.property_type_code not in RESIDENTIAL
        or (prop.bedrooms is not None and prop.bathrooms is not None),
        "price": prop.price_on_request or prop.price_amount is not None,
        "amenities": len(prop.amenity_links) > 0,
        "english": bool(prop.title_en),
    }
    score = sum(weight for name, weight in QUALITY_CHECKS if passed[name])
    return {
        "score": score,
        "checks": [{"check": n, "passed": passed[n], "weight": w} for n, w in QUALITY_CHECKS],
        "suggestions": [n for n, _ in QUALITY_CHECKS if not passed[n]],
        "photo_count": len(photos),
    }


def listing_quality(db: Session, principal: Principal | None, prop: Property) -> AIEnvelope:
    report = quality_report(prop)
    return _analysis(
        db,
        principal,
        feature="listing.quality",
        kind="analysis",
        methodology="Weighted completeness checklist (title, description, photos, location, "
        "area, rooms, price, amenities, English translation).",
        result=report,
        property_id=prop.id,
        confidence=1.0,
        sources=["listing fields"],
    )


def duplicate_candidates(db: Session, prop: Property) -> list[dict[str, Any]]:
    found: dict[uuid.UUID, dict[str, Any]] = {}

    def add(pid: uuid.UUID, reason: str, detail: Any) -> None:
        entry = found.setdefault(pid, {"property_id": str(pid), "reasons": []})
        entry["reasons"].append({"reason": reason, "detail": detail})

    hashes = [m.perceptual_hash for m in prop.media if m.perceptual_hash is not None]
    if hashes:
        for h in hashes:
            distance = func.bit_count(cast(PropertyMedia.perceptual_hash.op("#")(h), _bit64()))
            rows = db.execute(
                select(PropertyMedia.property_id, distance)
                .where(
                    PropertyMedia.perceptual_hash.is_not(None),
                    PropertyMedia.property_id != prop.id,
                    distance <= 6,
                )
                .limit(20)
            ).all()
            for pid, dist in rows:
                add(pid, "similar_photo", {"hamming_distance": int(dist)})
    text_rows = db.execute(
        select(Property.id, func.similarity(Property.search_text, prop_search_text(db, prop)))
        .where(
            Property.id != prop.id,
            Property.deleted_at.is_(None),
            func.similarity(Property.search_text, prop_search_text(db, prop)) >= 0.75,
        )
        .limit(20)
    ).all()
    for pid, sim in text_rows:
        add(pid, "similar_text", {"similarity": round(float(sim), 2)})
    if prop.location is not None and prop.price_amount is not None:
        centre = _geog(select(Property.location).where(Property.id == prop.id).scalar_subquery())
        near = db.execute(
            select(Property.id).where(
                Property.id != prop.id,
                Property.deleted_at.is_(None),
                Property.property_type_code == prop.property_type_code,
                Property.currency == prop.currency,
                Property.price_amount == prop.price_amount,
                Property.location.is_not(None),
                func.ST_DWithin(_geog(Property.location), centre, 50),
            )
        ).scalars()
        for pid in near:
            add(pid, "same_place_and_price", {"within_m": 50})
    return list(found.values())


def _bit64() -> Any:
    from sqlalchemy.dialects.postgresql import BIT

    return BIT(64)


def prop_search_text(db: Session, prop: Property) -> Any:
    return select(Property.search_text).where(Property.id == prop.id).scalar_subquery()


def listing_duplicates(db: Session, principal: Principal | None, prop: Property) -> AIEnvelope:
    candidates = duplicate_candidates(db, prop)
    return _analysis(
        db,
        principal,
        feature="listing.duplicates",
        kind="analysis",
        methodology="Perceptual-hash photo matches (Hamming distance ≤ 6), trigram text "
        "similarity ≥ 0.75, and same type/price within 50 m.",
        result={"candidates": candidates, "count": len(candidates)},
        property_id=prop.id,
        sources=["listing photos and text"],
        limitations=["Candidates need human review; similarity is not proof of duplication."],
    )


_CONTACT_IN_TEXT = re.compile(r"(\+?964|07\d)[\d\s-]{7,}|https?://|www\.|@[a-z0-9_]{3,}", re.I)


def risk_signals(db: Session, principal: Principal | None, prop: Property) -> AIEnvelope:
    signals: list[dict[str, Any]] = []
    comps, _ = comparables(db, prop)
    per_m2 = _per_m2(comps)
    if prop.area_m2 and prop.price_amount and len(per_m2) >= MIN_COMPARABLES:
        median = Decimal(statistics.median(per_m2))
        ratio = (
            (Decimal(prop.price_amount) / Decimal(prop.area_m2)) / median if median else Decimal(1)
        )
        if ratio < Decimal("0.4"):
            signals.append(
                {
                    "signal": "price_far_below_comparables",
                    "severity": "high",
                    "detail": {"ratio_to_median": str(_q2(ratio))},
                }
            )
    other_listers = {
        c["property_id"]
        for c in duplicate_candidates(db, prop)
        if any(r["reason"] == "similar_photo" for r in c["reasons"])
    }
    if other_listers:
        owners = db.execute(
            select(Property.lister_id).where(Property.id.in_([uuid.UUID(x) for x in other_listers]))
        ).scalars()
        if any(o != prop.lister_id for o in owners):
            signals.append(
                {
                    "signal": "photos_used_by_another_lister",
                    "severity": "high",
                    "detail": {"listings": sorted(other_listers)},
                }
            )
    if _CONTACT_IN_TEXT.search(f"{prop.description_ar} {prop.description_en or ''}"):
        signals.append(
            {"signal": "contact_details_in_description", "severity": "medium", "detail": None}
        )
    lister = db.get(User, prop.lister_id)
    if lister is not None and lister.created_at >= _now() - timedelta(days=7):
        recent = db.execute(
            select(func.count()).where(
                Property.lister_id == lister.id, Property.deleted_at.is_(None)
            )
        ).scalar_one()
        if recent >= 5:
            signals.append(
                {
                    "signal": "new_account_many_listings",
                    "severity": "medium",
                    "detail": {"listings": recent},
                }
            )
    if not any(m.kind == "IMAGE" for m in prop.media):
        signals.append({"signal": "no_photos", "severity": "low", "detail": None})
    weights = {"high": 3, "medium": 2, "low": 1}
    total = sum(weights[s["severity"]] for s in signals)
    level = "high" if total >= 3 else "medium" if total >= 2 else "low" if total else "none"
    return _analysis(
        db,
        principal,
        feature="listing.risk",
        kind="analysis",
        methodology="Rule-based signals: price per m² below 40% of the comparable median, photos "
        "matching another lister's, contact details in the text, new accounts with many listings, "
        "missing photos.",
        result={"risk_level": level, "signals": signals},
        property_id=prop.id,
        sources=["listing data", "comparable listings"],
        limitations=["Signals support moderators; they are not a verdict about the lister."],
    )


# --- similarity & recommendations


def _similarity(a: Property, b: Property, distance_m: float | None) -> tuple[float, list[str]]:
    score, reasons = 0.0, []
    if a.price_amount and b.price_amount and a.currency == b.currency:
        ratio = float(min(a.price_amount, b.price_amount) / max(a.price_amount, b.price_amount))
        score += 0.35 * ratio
        if ratio >= 0.8:
            reasons.append("similar_price")
    if a.area_m2 and b.area_m2:
        ratio = float(min(a.area_m2, b.area_m2) / max(a.area_m2, b.area_m2))
        score += 0.25 * ratio
        if ratio >= 0.8:
            reasons.append("similar_area")
    if a.bedrooms is not None and b.bedrooms is not None:
        score += 0.15 * max(0.0, 1 - abs(a.bedrooms - b.bedrooms) / 3)
        if a.bedrooms == b.bedrooms:
            reasons.append("same_bedrooms")
    if distance_m is not None:
        score += 0.25 * max(0.0, 1 - distance_m / 10_000)
        if distance_m <= 2000:
            reasons.append("nearby")
    elif a.district_id and a.district_id == b.district_id:
        score += 0.2
        reasons.append("same_district")
    elif a.city_id == b.city_id:
        score += 0.1
        reasons.append("same_city")
    return round(min(score, 1.0), 3), reasons


def similar_properties(
    db: Session, principal: Principal | None, prop: Property, limit: int = 8
) -> AIEnvelope:
    stmt = select(Property).where(
        Property.id != prop.id,
        Property.status == "APPROVED",
        Property.deleted_at.is_(None),
        Property.property_type_code == prop.property_type_code,
        Property.purpose == prop.purpose,
        Property.currency == prop.currency,
        Property.city_id == prop.city_id,
    )
    rows: list[tuple[Property, Any]]
    if prop.display_location is not None:
        centre = _geog(
            select(Property.display_location).where(Property.id == prop.id).scalar_subquery()
        )
        distance = func.ST_Distance(_geog(Property.display_location), centre)
        rows = [(r[0], r[1]) for r in db.execute(stmt.add_columns(distance).limit(200)).all()]
    else:
        rows = [(p, None) for p in db.execute(stmt.limit(200)).scalars()]
    scored: list[tuple[float, dict[str, Any]]] = []
    for other, dist in rows:
        score, reasons = _similarity(prop, other, float(dist) if dist is not None else None)
        scored.append((score, {"property_id": str(other.id), "score": score, "reasons": reasons}))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return _analysis(
        db,
        principal,
        feature="property.similar",
        kind="ranking",
        methodology="Same type, purpose, currency and city; ranked by price and area ratios, "
        "bedroom difference and distance between public locations.",
        result={"items": [item for _, item in scored[:limit]]},
        property_id=prop.id,
        sources=["public listings on this platform"],
    )


def recommendations(db: Session, principal: Principal, limit: int = 12) -> AIEnvelope:
    from app.favorites import Favorite
    from app.search.saved import SavedSearch

    fav_ids = list(
        db.execute(
            select(Favorite.property_id)
            .where(Favorite.user_id == principal.id)
            .order_by(Favorite.created_at.desc())
            .limit(20)
        ).scalars()
    )
    favs = (
        list(db.execute(select(Property).where(Property.id.in_(fav_ids))).scalars())
        if fav_ids
        else []
    )
    saved = list(
        db.execute(select(SavedSearch).where(SavedSearch.user_id == principal.id)).scalars()
    )
    types = {p.property_type_code for p in favs}
    purposes = {p.purpose for p in favs}
    cities = {p.city_id for p in favs}
    for s in saved:
        types.update(s.filters.get("property_types") or [])
        if s.filters.get("purpose"):
            purposes.add(s.filters["purpose"])
        if s.filters.get("city_id"):
            cities.add(uuid.UUID(s.filters["city_id"]))
    stmt = select(Property).where(
        Property.status == "APPROVED",
        Property.deleted_at.is_(None),
        Property.id.not_in(fav_ids) if fav_ids else Property.id.is_not(None),
    )
    basis: list[str] = []
    if types or purposes or cities:
        conditions = []
        if types:
            conditions.append(Property.property_type_code.in_(types))
            basis.append("property_types")
        if purposes:
            conditions.append(Property.purpose.in_(purposes))
            basis.append("purposes")
        if cities:
            conditions.append(Property.city_id.in_(cities))
            basis.append("cities")
        stmt = stmt.where(or_(*conditions))
    candidates = list(db.execute(stmt.order_by(Property.published_at.desc()).limit(200)).scalars())

    def score(p: Property) -> float:
        value = 0.0
        value += 0.4 if p.property_type_code in types else 0
        value += 0.3 if p.purpose in purposes else 0
        value += 0.2 if p.city_id in cities else 0
        value += 0.1 if p.verified_at else 0
        return value

    ranked = sorted(
        candidates, key=lambda p: (score(p), p.published_at or p.created_at), reverse=True
    )
    items = [{"property_id": str(p.id), "score": round(score(p), 2)} for p in ranked[:limit]]
    return _analysis(
        db,
        principal,
        feature="recommendations",
        kind="ranking",
        methodology="Matches your favorites and saved searches by type, purpose and city "
        "(newest first); without history, the newest listings are shown.",
        result={"items": items, "basis": basis or ["newest_listings"]},
        sources=["your favorites", "your saved searches", "public listings"],
    )


# --- neighbourhood & scoring


def neighborhood_analysis(db: Session, principal: Principal | None, prop: Property) -> AIEnvelope:
    from app.geo.pois import PointOfInterest

    poi_counts: dict[str, int] = {}
    if prop.display_location is not None:
        centre = _geog(
            select(Property.display_location).where(Property.id == prop.id).scalar_subquery()
        )
        rows = db.execute(
            select(PointOfInterest.category, func.count())
            .where(
                PointOfInterest.is_active.is_(True),
                func.ST_DWithin(_geog(PointOfInterest.location), centre, 1500),
            )
            .group_by(PointOfInterest.category)
        ).all()
        poi_counts = {c: int(n) for c, n in rows}
    area_filter = (
        Property.district_id == prop.district_id
        if prop.district_id
        else Property.city_id == prop.city_id
    )
    stats_rows = db.execute(
        select(Property.purpose, Property.currency, Property.price_amount, Property.area_m2).where(
            Property.status == "APPROVED",
            Property.deleted_at.is_(None),
            area_filter,
            # demo data never informs statistics about real listings
            Property.is_demo.is_(False) if not prop.is_demo else Property.id.is_not(None),
        )
    ).all()
    groups: dict[str, list[Decimal]] = {}
    counts: dict[str, int] = {}
    for purpose, currency, price, area in stats_rows:
        key = f"{purpose}:{currency}"
        counts[key] = counts.get(key, 0) + 1
        if price is not None and area:
            groups.setdefault(key, []).append(Decimal(price) / Decimal(area))
    market = []
    for key in sorted(counts):
        purpose, currency = key.split(":")
        values = groups.get(key, [])
        median = (
            str(_q2(Decimal(statistics.median(values)))) if len(values) >= MIN_COMPARABLES else None
        )
        market.append(
            {
                "purpose": purpose,
                "currency": currency,
                "active_listings": counts[key],
                "median_price_per_m2": median,
            }
        )
    return _analysis(
        db,
        principal,
        feature="neighborhood.analysis",
        kind="analysis",
        methodology="Counts of recorded points of interest within 1.5 km of the public location, "
        "and asking-price statistics of public listings in the same district (or city).",
        result={
            "scope": "district" if prop.district_id else "city",
            "poi_counts": poi_counts,
            "market": market,
            "location_available": prop.display_location is not None,
        },
        property_id=prop.id,
        sources=["points of interest (see their sources)", "public listings on this platform"],
        limitations=[
            ASKING_PRICE_LIMITATION,
            "Only places recorded on the platform are counted; absence in the data does not mean "
            "absence on the ground.",
        ],
    )


DEFAULT_WEIGHTS = {
    "value": 1.0,
    "size": 1.0,
    "completeness": 1.0,
    "verification": 1.0,
    "amenities": 1.0,
    "proximity": 1.0,
}


def score_property(
    db: Session,
    principal: Principal | None,
    prop: Property,
    weights: dict[str, float],
    wanted_amenities: list[str],
    wanted_categories: list[str],
) -> AIEnvelope:
    from app.geo.pois import PointOfInterest

    w = {**DEFAULT_WEIGHTS, **{k: max(0.0, v) for k, v in weights.items()}}
    criteria: dict[str, float | None] = {}
    comps, _ = comparables(db, prop)
    per_m2 = _per_m2(comps)
    if prop.area_m2 and prop.price_amount and len(per_m2) >= MIN_COMPARABLES:
        median = Decimal(statistics.median(per_m2))
        own = Decimal(prop.price_amount) / Decimal(prop.area_m2)
        criteria["value"] = round(
            max(0.0, min(100.0, 50 + float((median - own) / median) * 100)), 1
        )
        areas = sorted(Decimal(p.area_m2) for p in comps if p.area_m2)
        rank = sum(1 for a in areas if a <= Decimal(prop.area_m2)) / len(areas)
        criteria["size"] = round(rank * 100, 1)
    else:
        criteria["value"] = None
        criteria["size"] = None
    criteria["completeness"] = float(quality_report(prop)["score"])
    criteria["verification"] = 100.0 if prop.verified_at else 0.0
    have = {link.amenity_code for link in prop.amenity_links}
    criteria["amenities"] = (
        round(100 * len(have & set(wanted_amenities)) / len(set(wanted_amenities)), 1)
        if wanted_amenities
        else None
    )
    if wanted_categories and prop.display_location is not None:
        centre = _geog(
            select(Property.display_location).where(Property.id == prop.id).scalar_subquery()
        )
        present = set(
            db.execute(
                select(PointOfInterest.category)
                .where(
                    PointOfInterest.category.in_(wanted_categories),
                    PointOfInterest.is_active.is_(True),
                    func.ST_DWithin(_geog(PointOfInterest.location), centre, 1000),
                )
                .distinct()
            ).scalars()
        )
        criteria["proximity"] = round(100 * len(present) / len(set(wanted_categories)), 1)
    else:
        criteria["proximity"] = None
    used = {k: v for k, v in criteria.items() if v is not None and w.get(k, 0) > 0}
    total_weight = sum(w[k] for k in used)
    overall = (
        round(sum(v * w[k] for k, v in used.items()) / total_weight, 1) if total_weight else None
    )
    return _analysis(
        db,
        principal,
        feature="property.score",
        kind="analysis",
        methodology="Weighted average of available criteria (0–100): value = price per m² vs "
        "comparable median; size = area percentile among comparables; completeness = listing "
        "quality; verification; requested amenities present; requested POI categories within 1 km.",
        result={
            "overall": overall,
            "criteria": criteria,
            "weights": {k: w[k] for k in criteria},
            "excluded": sorted(k for k in criteria if k not in used),
        },
        property_id=prop.id,
        confidence=round(len(used) / len(criteria), 2),
        sources=["listing data", "comparable listings", "points of interest"],
        limitations=["Criteria without data are excluded, not guessed.", ASKING_PRICE_LIMITATION],
    )


# --- leads


def lead_priority_score(
    db: Session, lead: Lead, prop: Property | None, stats: dict[str, Any]
) -> dict[str, Any]:
    factors: list[dict[str, Any]] = []
    score = 0.0
    now = _now()
    last = lead.last_activity_at or lead.created_at
    hours = (now - last).total_seconds() / 3600
    recency = 25 if hours <= 24 else 15 if hours <= 72 else 5 if hours <= 24 * 14 else 0
    score += recency
    factors.append({"factor": "recent_activity", "points": recency, "hours_since": round(hours, 1)})
    source_points = {"INQUIRY": 15, "REFERRAL": 15, "WALK_IN": 12, "PHONE": 10, "WHATSAPP": 10}.get(
        lead.source, 5
    )
    score += source_points
    factors.append({"factor": "source", "points": source_points, "value": lead.source})
    if lead.next_follow_up_at and lead.next_follow_up_at < now:
        score += 20
        factors.append({"factor": "overdue_follow_up", "points": 20})
    if (
        lead.budget_currency
        and prop
        and prop.price_amount
        and prop.currency == lead.budget_currency
    ):
        fits = (lead.budget_max is None or prop.price_amount <= lead.budget_max) and (
            lead.budget_min is None or prop.price_amount >= lead.budget_min
        )
        points = 20 if fits else 0
        score += points
        factors.append({"factor": "budget_fits_listing", "points": points})
    stage_points = {"NEGOTIATION": 20, "VIEWING": 15, "QUALIFIED": 10, "CONTACTED": 5}.get(
        lead.status_code, 0
    )
    score += stage_points
    factors.append({"factor": "stage", "points": stage_points, "value": lead.status_code})
    inquiries = stats.get("inquiries", 0)
    if inquiries > 1:
        score += 5
        factors.append({"factor": "repeat_inquiries", "points": 5, "count": inquiries})
    if lead.priority == "HIGH":
        score += 10
        factors.append({"factor": "marked_high_priority", "points": 10})
    return {"lead_id": str(lead.id), "score": min(100, round(score)), "factors": factors}


def prioritize_leads(db: Session, principal: Principal, leads: list[Lead]) -> AIEnvelope:
    prop_ids = {lead.property_id for lead in leads if lead.property_id}
    props = (
        {p.id: p for p in db.execute(select(Property).where(Property.id.in_(prop_ids))).scalars()}
        if prop_ids
        else {}
    )
    counts = (
        dict(
            (row[0], int(row[1]))
            for row in db.execute(
                select(LeadActivity.lead_id, func.count())
                .where(
                    LeadActivity.lead_id.in_([lead.id for lead in leads]),
                    LeadActivity.kind == ActivityKind.INQUIRY,
                )
                .group_by(LeadActivity.lead_id)
            ).all()
        )
        if leads
        else {}
    )
    scored = [
        lead_priority_score(
            db,
            lead,
            props.get(lead.property_id) if lead.property_id else None,
            {"inquiries": counts.get(lead.id, 0)},
        )
        for lead in leads
    ]
    scored.sort(key=lambda s: s["score"], reverse=True)
    return _analysis(
        db,
        principal,
        feature="lead.priority",
        kind="ranking",
        methodology="Points for recent activity, source, overdue follow-up, budget fitting the "
        "listing (same currency only), pipeline stage, repeat inquiries and manual priority.",
        result={"items": scored},
        sources=["CRM data"],
        limitations=["A ranking aid, not a prediction of closing."],
    )


def lead_facts(db: Session, lead: Lead, principal: Principal) -> dict[str, Any]:
    from app.crm.models import Customer

    customer = db.get(Customer, lead.customer_id)
    prop = db.get(Property, lead.property_id) if lead.property_id else None
    status = db.get(LeadStatus, lead.status_code)
    activity_count = db.execute(
        select(func.count()).where(LeadActivity.lead_id == lead.id)
    ).scalar_one()
    facts: dict[str, Any] = {
        "customer_name": customer.full_name if customer else None,
        "property_title": prop.title_ar if prop else None,
        "property_listed": bool(prop and prop.is_public),
        "status": status.name_ar if status else lead.status_code,
        "activity_count": activity_count,
        "agent_name": principal.user.full_name,
    }
    return {k: v for k, v in facts.items() if v not in (None, "")}


def lead_reply_draft(db: Session, principal: Principal, lead: Lead, language: str) -> AIEnvelope:
    facts = lead_facts(db, lead, principal)
    data, row = generate(
        db,
        principal,
        feature="lead.reply",
        task="lead.reply",
        system="You help Iraqi real-estate agents reply to inquiries politely. Use only the "
        "facts provided; never state prices, availability dates or legal facts that are not "
        "in the facts.",
        instructions="Draft a short reply to the customer.",
        facts=facts,
        output_schema={
            "type": "object",
            "properties": {"reply": {"type": "string"}},
            "required": ["reply"],
        },
        validate=_require_str_fields("reply"),
        language=language,
        lead_id=lead.id,
    )
    return _envelope(
        row,
        kind="generated",
        methodology="Reply drafted from the lead and listing facts only.",
        result={"reply": data["reply"]},
        limitations=["Draft — review and edit before sending."],
    )


def lead_summary(db: Session, principal: Principal, lead: Lead, language: str) -> AIEnvelope:
    facts = lead_facts(db, lead, principal)
    data, row = generate(
        db,
        principal,
        feature="lead.summary",
        task="lead.summary",
        system="Summarize CRM lead information factually using only the facts provided.",
        instructions="Summarize the lead in one line.",
        facts=facts,
        output_schema={
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
        validate=_require_str_fields("summary"),
        language=language,
        lead_id=lead.id,
    )
    return _envelope(
        row,
        kind="generated",
        methodology="Summary of CRM fields only.",
        result={"summary": data["summary"]},
    )


# --- natural-language search


def search_vocabulary(db: Session) -> dict[str, Any]:
    from app.geo.models import Governorate

    def entries(model: Any) -> list[dict[str, Any]]:
        return [
            {"id": str(r.id), "names": [r.name_ar, r.name_en]}
            for r in db.execute(select(model).where(model.is_active.is_(True))).scalars()
        ]

    return {
        "governorates": entries(Governorate),
        "cities": entries(City),
        "districts": entries(District),
        "neighborhoods": entries(Neighborhood),
    }


def parse_search(db: Session, principal: Principal | None, query: str) -> AIEnvelope:
    from app.search.schemas import SearchFilters

    facts = {"query": query, "vocabulary": search_vocabulary(db)}

    def check(data: dict[str, Any]) -> list[str]:
        if not isinstance(data.get("filters"), dict):
            return ["missing_or_invalid:filters"]
        try:
            SearchFilters.model_validate(data["filters"])
        except ValueError as exc:
            return [f"invalid_filters:{type(exc).__name__}"]
        return []

    data, row = generate(
        db,
        principal,
        feature="search.parse",
        task="search.parse",
        system="Convert an Iraqi real-estate search request into structured filters. Use place "
        "ids only from the vocabulary. Never guess a currency: if none is stated, leave price "
        "filters out and report the ambiguity.",
        instructions="Return filters, understood (list of {field,value,phrase}), ambiguities, "
        "unparsed and confidence (0-1).",
        facts=facts,
        output_schema={
            "type": "object",
            "properties": {
                "filters": {"type": "object"},
                "understood": {"type": "array"},
                "ambiguities": {"type": "array"},
                "unparsed": {"type": "string"},
                "confidence": {"type": "number"},
            },
            "required": ["filters"],
        },
        validate=check,
        guard_text=False,
        kind="extraction",
    )
    filters = SearchFilters.model_validate(data["filters"])
    confidence = data.get("confidence")
    return _envelope(
        row,
        kind="extraction",
        methodology="Search request mapped to structured filters (place names, types, purpose, "
        "rooms, area, price with explicit currency, amenities).",
        result={
            "filters": filters.model_dump(mode="json", exclude_defaults=True),
            "understood": data.get("understood", []),
            "ambiguities": data.get("ambiguities", []),
            "unparsed": data.get("unparsed", ""),
        },
        confidence=float(confidence) if isinstance(confidence, int | float) else None,
        limitations=["Check the interpreted filters; unparsed words are ignored."],
    )
