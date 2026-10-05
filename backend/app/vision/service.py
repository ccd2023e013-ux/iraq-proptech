"""AI Property Vision: briefs → labelled concept images (CURRENT → CONCEPT → VISION)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import Principal
from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError
from app.storage import get_storage
from app.vision.models import VisionConcept
from app.vision.providers import (
    MockVisionProvider,
    VisionProviderError,
    clean_notes,
    get_vision_provider,
)
from app.vision.render import LABEL, Brief

LABEL_AR = "تصوّر بالذكاء الاصطناعي — ليس موافقة هندسية أو حكومية"

ASSUMPTIONS = [
    "building_coverage_by_type",
    "floor_height_3_3_m",
    "no_setbacks_or_regulations_applied",
]
LIMITATIONS = [
    "not_structural_or_engineering_design",
    "not_legal_or_planning_approval",
    "not_a_cost_or_value_estimate",
]


class ConceptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_id: uuid.UUID | None = None
    building_type: Literal["house", "villa", "apartments", "commercial", "mixed_use"] = "house"
    floors: int = Field(default=2, ge=1, le=12)
    style: Literal["modern", "traditional", "courtyard", "minimal"] = "modern"
    plot_width_m: float = Field(default=15, ge=6, le=200)
    plot_depth_m: float = Field(default=25, ge=6, le=200)
    landscaping: bool = True
    parking: bool = True
    pool: bool = False
    shops_ground_floor: bool = False
    notes: str | None = Field(default=None, max_length=300)


class ConceptOut(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID | None
    brief: dict[str, Any]
    notes: str | None
    provider: str
    model: str
    status: str
    label_en: str
    label_ar: str
    images: dict[str, str]
    assumptions: list[str]
    limitations: list[str]
    created_at: datetime


def _out(row: VisionConcept) -> ConceptOut:
    base = f"/api/v1/vision/concepts/{row.id}/image"
    return ConceptOut(
        id=row.id,
        property_id=row.property_id,
        brief=row.brief,
        notes=row.notes,
        provider=row.provider,
        model=row.model,
        status=row.status,
        label_en=LABEL,
        label_ar=LABEL_AR,
        images={"concept": f"{base}?variant=concept", "vision": f"{base}?variant=vision"},
        assumptions=ASSUMPTIONS,
        limitations=LIMITATIONS,
        created_at=row.created_at,
    )


def _check_quota(db: Session, principal: Principal) -> None:
    limit = get_settings().vision_daily_limit_per_user
    if limit == 0:
        return
    used = db.execute(
        select(func.count()).where(
            VisionConcept.user_id == principal.id,
            VisionConcept.created_at >= datetime.now(UTC) - timedelta(days=1),
        )
    ).scalar_one()
    if used >= limit:
        raise AppError(
            "Daily concept limit reached. Try again tomorrow.",
            code="VISION_QUOTA_EXCEEDED",
            status_code=429,
        )


def create_concept(db: Session, principal: Principal, body: ConceptIn) -> ConceptOut:
    _check_quota(db, principal)
    brief = Brief(
        building_type=body.building_type,
        floors=body.floors,
        style=body.style,
        plot_width_m=round(body.plot_width_m, 1),
        plot_depth_m=round(body.plot_depth_m, 1),
        landscaping=body.landscaping,
        parking=body.parking,
        pool=body.pool,
        shops_ground_floor=body.shops_ground_floor,
    )
    notes = clean_notes(body.notes)
    provider = get_vision_provider()
    status = "SUCCEEDED"
    try:
        concept = provider.generate(brief, "concept", notes)
        vision = provider.generate(brief, "vision", notes)
    except VisionProviderError:
        # Fall back to the offline renderer; the record says so.
        status = "FALLBACK"
        mock = MockVisionProvider()
        concept = mock.generate(brief, "concept", notes)
        vision = mock.generate(brief, "vision", notes)
    row = VisionConcept(
        id=uuid.uuid4(),
        user_id=principal.id,
        property_id=body.property_id,
        brief={k: v for k, v in body.model_dump().items() if k not in ("notes", "property_id")},
        notes=notes,
        provider=concept.provider,
        model=concept.model,
        status=status,
        concept_key="",
        vision_key="",
        latency_ms=concept.latency_ms + vision.latency_ms,
    )
    row.concept_key = f"vision/{row.id}/concept.png"
    row.vision_key = f"vision/{row.id}/vision.png"
    storage = get_storage()
    storage.put(row.concept_key, concept.png, "image/png")
    storage.put(row.vision_key, vision.png, "image/png")
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(row)


def get_owned(db: Session, principal: Principal, concept_id: uuid.UUID) -> VisionConcept:
    row = db.get(VisionConcept, concept_id)
    if row is None or row.user_id != principal.id:
        # Not found either way: never reveal other people's concepts.
        raise NotFoundError("Concept not found", code="CONCEPT_NOT_FOUND")
    return row


def list_mine(db: Session, principal: Principal, limit: int = 20) -> list[ConceptOut]:
    rows = db.execute(
        select(VisionConcept)
        .where(VisionConcept.user_id == principal.id)
        .order_by(VisionConcept.created_at.desc())
        .limit(limit)
    ).scalars()
    return [_out(r) for r in rows]


def concept_out(row: VisionConcept) -> ConceptOut:
    return _out(row)
