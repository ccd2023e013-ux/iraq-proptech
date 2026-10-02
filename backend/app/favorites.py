"""Favorites (saved properties)."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy import DateTime, ForeignKey, func, select
from sqlalchemy.dialects.postgresql import UUID, insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.auth.deps import Principal, require_permission
from app.core.errors import NotFoundError
from app.core.pagination import Page, PageParams, page_params
from app.db.base import Base
from app.db.session import get_db
from app.properties.enums import PropertyStatus
from app.properties.models import Property
from app.properties.presenter import to_cards
from app.properties.schemas import PropertyCard
from app.rbac.catalog import Permission


class Favorite(Base):
    __tablename__ = "favorites"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


router = APIRouter(tags=["favorites"])
_manage = require_permission(Permission.FAVORITES_MANAGE)


@router.put("/properties/{property_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def add_favorite(
    property_id: uuid.UUID, principal: Principal = Depends(_manage), db: Session = Depends(get_db)
) -> None:
    prop = db.get(Property, property_id)
    if prop is None or not prop.is_public:
        raise NotFoundError("Property not found", code="PROPERTY_NOT_FOUND")
    db.execute(
        insert(Favorite)
        .values(user_id=principal.id, property_id=property_id)
        .on_conflict_do_nothing()  # idempotent
    )
    db.commit()


@router.delete("/properties/{property_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    property_id: uuid.UUID, principal: Principal = Depends(_manage), db: Session = Depends(get_db)
) -> None:
    favorite = db.get(Favorite, (principal.id, property_id))
    if favorite is not None:
        db.delete(favorite)
        db.commit()


@router.get("/me/favorites", response_model=Page[PropertyCard])
def list_favorites(
    params: PageParams = Depends(page_params),
    principal: Principal = Depends(_manage),
    db: Session = Depends(get_db),
) -> Page[PropertyCard]:
    """Saved listings that are still public (sold/removed ones drop out automatically)."""
    stmt = (
        select(Property)
        .join(Favorite, Favorite.property_id == Property.id)
        .where(
            Favorite.user_id == principal.id,
            Property.deleted_at.is_(None),
            Property.status == PropertyStatus.APPROVED,
        )
    )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(Favorite.created_at.desc()).offset(params.offset).limit(params.page_size)
    ).scalars()
    return Page(
        items=to_cards(db, list(rows)), total=total, page=params.page, page_size=params.page_size
    )


@router.get("/me/favorites/ids", response_model=list[uuid.UUID])
def favorite_ids(
    principal: Principal = Depends(_manage), db: Session = Depends(get_db)
) -> list[uuid.UUID]:
    return list(
        db.execute(select(Favorite.property_id).where(Favorite.user_id == principal.id)).scalars()
    )
