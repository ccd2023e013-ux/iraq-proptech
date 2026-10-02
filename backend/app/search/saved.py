"""Saved searches: a named, validated ``SearchFilters`` per user, with an alert
frequency. Alert delivery (new matching listings) is handled by the
notifications worker; this module stores the search and the watermark of what
the user has already been told about.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.audit import service as audit
from app.auth.deps import Principal, require_permission
from app.core.errors import AppError, NotFoundError
from app.core.pagination import PageParams, page_params
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.session import get_db
from app.properties.models import Property
from app.properties.presenter import to_cards
from app.rbac.catalog import Permission
from app.search import service as search_service
from app.search.router import SearchResult, validate_filters
from app.search.schemas import SearchFilters

MAX_SAVED_SEARCHES = 20


class AlertFrequency(StrEnum):
    NONE = "NONE"
    INSTANT = "INSTANT"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


class SavedSearch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "saved_searches"
    __table_args__ = (
        CheckConstraint(
            "alert_frequency IN ('NONE','INSTANT','DAILY','WEEKLY')", name="frequency_valid"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    alert_frequency: Mapped[str] = mapped_column(
        String(8), nullable=False, default=AlertFrequency.DAILY
    )
    # Listings published at or before this instant were already notified/seen.
    last_alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SavedSearchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    filters: dict[str, Any]
    alert_frequency: AlertFrequency = AlertFrequency.DAILY


class SavedSearchUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    filters: dict[str, Any] | None = None
    alert_frequency: AlertFrequency | None = None


class SavedSearchOut(BaseModel):
    id: uuid.UUID
    name: str
    filters: SearchFilters
    alert_frequency: str
    last_alerted_at: datetime | None
    created_at: datetime
    new_matches: int = Field(description="Public listings published since the last alert")


def _normalized(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and store the canonical form (also drops pagination-only keys)."""
    filters = validate_filters(raw)
    return filters.model_dump(mode="json", exclude_defaults=True)


def new_matches_count(db: Session, saved: SavedSearch) -> int:
    filters = SearchFilters.model_validate(saved.filters)
    stmt, _ = search_service.build_query(filters)
    since = saved.last_alerted_at or saved.created_at
    stmt = stmt.order_by(None).where(Property.published_at > since)
    return db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()


def _out(db: Session, saved: SavedSearch) -> SavedSearchOut:
    return SavedSearchOut(
        id=saved.id,
        name=saved.name,
        filters=SearchFilters.model_validate(saved.filters),
        alert_frequency=saved.alert_frequency,
        last_alerted_at=saved.last_alerted_at,
        created_at=saved.created_at,
        new_matches=new_matches_count(db, saved),
    )


router = APIRouter(tags=["saved-searches"])
_manage = require_permission(Permission.SAVED_SEARCHES_MANAGE)


def _get(db: Session, principal: Principal, saved_id: uuid.UUID) -> SavedSearch:
    saved = db.get(SavedSearch, saved_id)
    if saved is None or saved.user_id != principal.id:  # never reveal others' searches
        raise NotFoundError("Saved search not found", code="SAVED_SEARCH_NOT_FOUND")
    return saved


@router.get("/me/saved-searches", response_model=list[SavedSearchOut])
def list_saved(
    principal: Principal = Depends(_manage), db: Session = Depends(get_db)
) -> list[SavedSearchOut]:
    rows = db.execute(
        select(SavedSearch)
        .where(SavedSearch.user_id == principal.id)
        .order_by(SavedSearch.created_at.desc())
    ).scalars()
    return [_out(db, s) for s in rows]


@router.post(
    "/me/saved-searches", response_model=SavedSearchOut, status_code=status.HTTP_201_CREATED
)
def create_saved(
    body: SavedSearchIn, principal: Principal = Depends(_manage), db: Session = Depends(get_db)
) -> SavedSearchOut:
    count = db.execute(select(func.count()).where(SavedSearch.user_id == principal.id)).scalar_one()
    if count >= MAX_SAVED_SEARCHES:
        raise AppError(
            f"You can keep up to {MAX_SAVED_SEARCHES} saved searches",
            code="SAVED_SEARCH_LIMIT",
            status_code=409,
        )
    saved = SavedSearch(
        user_id=principal.id,
        name=body.name.strip(),
        filters=_normalized(body.filters),
        alert_frequency=body.alert_frequency,
        last_alerted_at=datetime.now(UTC),
    )
    db.add(saved)
    db.flush()
    audit.record(
        db,
        "saved_search.created",
        actor_id=principal.id,
        resource_type="saved_search",
        resource_id=saved.id,
    )
    db.commit()
    db.refresh(saved)
    return _out(db, saved)


@router.patch("/me/saved-searches/{saved_id}", response_model=SavedSearchOut)
def update_saved(
    saved_id: uuid.UUID,
    body: SavedSearchUpdate,
    principal: Principal = Depends(_manage),
    db: Session = Depends(get_db),
) -> SavedSearchOut:
    saved = _get(db, principal, saved_id)
    if body.name is not None:
        saved.name = body.name.strip()
    if body.filters is not None:
        saved.filters = _normalized(body.filters)
    if body.alert_frequency is not None:
        saved.alert_frequency = body.alert_frequency
    db.commit()
    db.refresh(saved)
    return _out(db, saved)


@router.delete("/me/saved-searches/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved(
    saved_id: uuid.UUID, principal: Principal = Depends(_manage), db: Session = Depends(get_db)
) -> None:
    saved = _get(db, principal, saved_id)
    db.delete(saved)
    db.commit()


@router.get("/me/saved-searches/{saved_id}/results", response_model=SearchResult)
def saved_results(
    saved_id: uuid.UUID,
    params: PageParams = Depends(page_params),
    principal: Principal = Depends(_manage),
    db: Session = Depends(get_db),
) -> SearchResult:
    """Run the saved search; viewing results marks current matches as seen."""
    saved = _get(db, principal, saved_id)
    filters = SearchFilters.model_validate(saved.filters)
    rows, total = search_service.search(db, filters, offset=params.offset, limit=params.page_size)
    saved.last_alerted_at = datetime.now(UTC)
    db.commit()
    return SearchResult(
        items=to_cards(db, rows),
        total=total,
        page=params.page,
        page_size=params.page_size,
        filters=filters,
    )
