"""/api/v1/ai — explainable AI features (mock provider by default)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import service
from app.ai.models import AIGeneration
from app.ai.schemas import (
    AIEnvelope,
    DescriptionRequest,
    ImproveTextRequest,
    ReplyDraftRequest,
    ScoreRequest,
    SearchParseRequest,
)
from app.auth.deps import (
    Principal,
    get_optional_principal,
    get_principal,
    require_any_permission,
    require_permission,
)
from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.core.pagination import Page, PageParams, page_params
from app.core.rate_limit import rate_limit
from app.crm import policies as crm_policies
from app.crm import service as crm_service
from app.db.session import get_db
from app.policies import can_view_private_property
from app.properties.models import Property
from app.properties.presenter import to_cards
from app.properties.schemas import PropertyCard
from app.properties.service import get_property_or_404, manages
from app.rbac.catalog import Permission
from app.search import service as search_service
from app.search.schemas import SearchFilters

router = APIRouter(tags=["ai"])

_public_limit = rate_limit("ai-public", limit=120, window=3600)
_generative_limit = rate_limit("ai-generate", limit=60, window=3600)


def _visible(db: Session, principal: Principal | None, property_id: uuid.UUID) -> Property:
    prop = get_property_or_404(db, property_id)
    if prop.is_public or can_view_private_property(
        db, principal, lister_id=prop.lister_id, agency_id=prop.agency_id, agent_id=prop.agent_id
    ):
        return prop
    raise NotFoundError("Property not found", code="PROPERTY_NOT_FOUND")


def _managed(db: Session, principal: Principal, property_id: uuid.UUID) -> Property:
    prop = get_property_or_404(db, property_id)
    if manages(db, principal, prop):
        return prop
    if prop.is_public:
        raise PermissionDeniedError("You cannot use AI tools on this listing")
    raise NotFoundError("Property not found", code="PROPERTY_NOT_FOUND")


def _moderator_or_manager(db: Session, principal: Principal, property_id: uuid.UUID) -> Property:
    prop = get_property_or_404(db, property_id)
    if principal.has(Permission.PROPERTIES_MODERATE) or manages(db, principal, prop):
        return prop
    raise NotFoundError("Property not found", code="PROPERTY_NOT_FOUND")


# --- listing authoring (generative)


@router.post(
    "/ai/listings/{property_id}/description",
    response_model=AIEnvelope,
    dependencies=[Depends(_generative_limit)],
)
def ai_description(
    property_id: uuid.UUID,
    body: DescriptionRequest,
    principal: Principal = Depends(require_permission(Permission.AI_AUTHOR)),
    db: Session = Depends(get_db),
) -> AIEnvelope:
    return service.describe_listing(
        db, principal, _managed(db, principal, property_id), body.language
    )


@router.post(
    "/ai/listings/{property_id}/title",
    response_model=AIEnvelope,
    dependencies=[Depends(_generative_limit)],
)
def ai_title(
    property_id: uuid.UUID,
    body: DescriptionRequest,
    principal: Principal = Depends(require_permission(Permission.AI_AUTHOR)),
    db: Session = Depends(get_db),
) -> AIEnvelope:
    return service.title_listing(db, principal, _managed(db, principal, property_id), body.language)


@router.post(
    "/ai/text/improve-arabic", response_model=AIEnvelope, dependencies=[Depends(_generative_limit)]
)
def ai_improve(
    body: ImproveTextRequest,
    principal: Principal = Depends(require_permission(Permission.AI_AUTHOR)),
    db: Session = Depends(get_db),
) -> AIEnvelope:
    return service.improve_arabic(db, principal, body.text)


@router.get(
    "/ai/listings/{property_id}/quality",
    response_model=AIEnvelope,
)
def ai_quality(
    property_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> AIEnvelope:
    return service.listing_quality(db, principal, _moderator_or_manager(db, principal, property_id))


@router.get("/ai/listings/{property_id}/duplicates", response_model=AIEnvelope)
def ai_duplicates(
    property_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> AIEnvelope:
    return service.listing_duplicates(
        db, principal, _moderator_or_manager(db, principal, property_id)
    )


@router.get("/ai/listings/{property_id}/risk", response_model=AIEnvelope)
def ai_risk(
    property_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.PROPERTIES_MODERATE)),
    db: Session = Depends(get_db),
) -> AIEnvelope:
    return service.risk_signals(db, principal, get_property_or_404(db, property_id))


# --- property insights (public)


@router.get(
    "/ai/properties/{property_id}/summary",
    response_model=AIEnvelope,
    dependencies=[Depends(_public_limit)],
)
def ai_summary(
    property_id: uuid.UUID,
    language: str = Query("ar", pattern="^(ar|en)$"),
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> AIEnvelope:
    return service.summarize_property(db, principal, _visible(db, principal, property_id), language)


@router.get(
    "/ai/properties/{property_id}/price-analysis",
    response_model=AIEnvelope,
    dependencies=[Depends(_public_limit)],
)
def ai_price(
    property_id: uuid.UUID,
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> AIEnvelope:
    return service.price_analysis(db, principal, _visible(db, principal, property_id))


@router.get(
    "/ai/properties/{property_id}/investment",
    response_model=AIEnvelope,
    dependencies=[Depends(_public_limit)],
)
def ai_investment(
    property_id: uuid.UUID,
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> AIEnvelope:
    return service.investment_analysis(db, principal, _visible(db, principal, property_id))


@router.get(
    "/ai/properties/{property_id}/neighborhood",
    response_model=AIEnvelope,
    dependencies=[Depends(_public_limit)],
)
def ai_neighborhood(
    property_id: uuid.UUID,
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> AIEnvelope:
    return service.neighborhood_analysis(db, principal, _visible(db, principal, property_id))


class SimilarOut(BaseModel):
    envelope: AIEnvelope
    items: list[PropertyCard]


@router.get(
    "/ai/properties/{property_id}/similar",
    response_model=SimilarOut,
    dependencies=[Depends(_public_limit)],
)
def ai_similar(
    property_id: uuid.UUID,
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> SimilarOut:
    envelope = service.similar_properties(db, principal, _visible(db, principal, property_id))
    return SimilarOut(envelope=envelope, items=_cards(db, envelope.result["items"]))


@router.post(
    "/ai/properties/{property_id}/score",
    response_model=AIEnvelope,
    dependencies=[Depends(_public_limit)],
)
def ai_score(
    property_id: uuid.UUID,
    body: ScoreRequest,
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> AIEnvelope:
    prop = _visible(db, principal, property_id)
    return service.score_property(
        db,
        principal,
        prop,
        {str(k): v for k, v in body.weights.items()},
        body.wanted_amenities,
        body.wanted_poi_categories,
    )


def _cards(db: Session, items: list[dict[str, Any]]) -> list[PropertyCard]:
    ids = [uuid.UUID(i["property_id"]) for i in items]
    if not ids:
        return []
    found = {p.id: p for p in db.execute(select(Property).where(Property.id.in_(ids))).scalars()}
    return to_cards(db, [found[i] for i in ids if i in found])


class RecommendationsOut(BaseModel):
    envelope: AIEnvelope
    items: list[PropertyCard]


@router.get("/me/recommendations", response_model=RecommendationsOut)
def my_recommendations(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> RecommendationsOut:
    envelope = service.recommendations(db, principal)
    return RecommendationsOut(envelope=envelope, items=_cards(db, envelope.result["items"]))


@router.get("/ai/compare", response_model=AIEnvelope, dependencies=[Depends(_public_limit)])
def ai_compare(
    ids: str = Query(min_length=36, max_length=200, description="2–4 comma-separated listing ids"),
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> AIEnvelope:
    try:
        wanted = list(dict.fromkeys(uuid.UUID(part.strip()) for part in ids.split(",")))
    except ValueError as exc:
        raise AppError("Invalid listing id", code="INVALID_IDS", status_code=422) from exc
    if not 2 <= len(wanted) <= 4:
        raise AppError("Compare 2 to 4 listings", code="INVALID_IDS", status_code=422)
    return service.compare_properties(db, principal, [_visible(db, principal, i) for i in wanted])


# --- natural-language search


@router.post("/ai/search/parse", response_model=AIEnvelope, dependencies=[Depends(_public_limit)])
def ai_parse(
    body: SearchParseRequest,
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> AIEnvelope:
    return service.parse_search(db, principal, body.query)


class NLSearchOut(BaseModel):
    interpretation: AIEnvelope
    items: list[PropertyCard]
    total: int
    page: int
    page_size: int


@router.get("/ai/search", response_model=NLSearchOut, dependencies=[Depends(_public_limit)])
def ai_search(
    q: str = Query(min_length=2, max_length=300),
    params: PageParams = Depends(page_params),
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> NLSearchOut:
    """Natural-language search: interpret, then run the structured search."""
    interpretation = service.parse_search(db, principal, q)
    filters = SearchFilters.model_validate(interpretation.result["filters"])
    rows, total = search_service.search(db, filters, offset=params.offset, limit=params.page_size)
    return NLSearchOut(
        interpretation=interpretation,
        items=to_cards(db, rows),
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


# --- CRM assistance

_crm_reader = require_any_permission(
    Permission.LEADS_READ_OWN, Permission.LEADS_READ_AGENCY, Permission.LEADS_READ_ANY
)


@router.get("/ai/leads/prioritized", response_model=AIEnvelope)
def ai_lead_priority(
    principal: Principal = Depends(_crm_reader), db: Session = Depends(get_db)
) -> AIEnvelope:
    leads, _ = crm_service.list_leads(
        db,
        principal,
        status=None,
        assigned_to_id=None,
        property_id=None,
        q=None,
        overdue=False,
        open_only=True,
        offset=0,
        limit=100,
    )
    return service.prioritize_leads(db, principal, leads)


@router.post(
    "/ai/leads/{lead_id}/reply-draft",
    response_model=AIEnvelope,
    dependencies=[Depends(_generative_limit)],
)
def ai_reply(
    lead_id: uuid.UUID,
    body: ReplyDraftRequest,
    principal: Principal = Depends(_crm_reader),
    db: Session = Depends(get_db),
) -> AIEnvelope:
    lead = crm_service.get_lead_or_404(db, principal, lead_id)
    if not crm_policies.can_manage_lead(db, principal, lead):
        raise PermissionDeniedError("You cannot work on this lead")
    return service.lead_reply_draft(db, principal, lead, body.language)


@router.post(
    "/ai/leads/{lead_id}/summary",
    response_model=AIEnvelope,
    dependencies=[Depends(_generative_limit)],
)
def ai_lead_summary(
    lead_id: uuid.UUID,
    body: ReplyDraftRequest,
    principal: Principal = Depends(_crm_reader),
    db: Session = Depends(get_db),
) -> AIEnvelope:
    lead = crm_service.get_lead_or_404(db, principal, lead_id)
    return service.lead_summary(db, principal, lead, body.language)


# --- administration


class GenerationOut(BaseModel):
    id: uuid.UUID
    feature: str
    kind: str
    provider: str
    model: str
    status: str
    user_id: uuid.UUID | None
    property_id: uuid.UUID | None
    lead_id: uuid.UUID | None
    validation_errors: list[str] | None
    confidence: float | None
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    created_at: datetime
    output: dict[str, Any] | None


@router.get("/admin/ai/generations", response_model=Page[GenerationOut])
def admin_generations(
    feature: str | None = Query(default=None, max_length=40),
    status: str | None = Query(default=None, max_length=10),
    params: PageParams = Depends(page_params),
    _: Principal = Depends(require_permission(Permission.AI_ADMIN)),
    db: Session = Depends(get_db),
) -> Page[GenerationOut]:
    stmt = select(AIGeneration)
    if feature:
        stmt = stmt.where(AIGeneration.feature == feature)
    if status:
        stmt = stmt.where(AIGeneration.status == status)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(AIGeneration.created_at.desc()).offset(params.offset).limit(params.page_size)
    ).scalars()
    items = [GenerationOut.model_validate(r, from_attributes=True) for r in rows]
    return Page(items=items, total=total, page=params.page, page_size=params.page_size)


class UsageRow(BaseModel):
    feature: str
    provider: str
    status: str
    calls: int
    input_tokens: int
    output_tokens: int
    avg_latency_ms: float


@router.get("/admin/ai/usage", response_model=list[UsageRow])
def admin_usage(
    days: int = Query(30, ge=1, le=365),
    _: Principal = Depends(require_permission(Permission.AI_ADMIN)),
    db: Session = Depends(get_db),
) -> list[UsageRow]:
    since = datetime.now(UTC) - timedelta(days=days)
    rows = db.execute(
        select(
            AIGeneration.feature,
            AIGeneration.provider,
            AIGeneration.status,
            func.count(),
            func.coalesce(func.sum(AIGeneration.input_tokens), 0),
            func.coalesce(func.sum(AIGeneration.output_tokens), 0),
            func.coalesce(func.avg(AIGeneration.latency_ms), 0),
        )
        .where(AIGeneration.created_at >= since)
        .group_by(AIGeneration.feature, AIGeneration.provider, AIGeneration.status)
        .order_by(func.count().desc())
    ).all()
    return [
        UsageRow(
            feature=r[0],
            provider=r[1],
            status=r[2],
            calls=int(r[3]),
            input_tokens=int(r[4]),
            output_tokens=int(r[5]),
            avg_latency_ms=round(float(r[6]), 1),
        )
        for r in rows
    ]
