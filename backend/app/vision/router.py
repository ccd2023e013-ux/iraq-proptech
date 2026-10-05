"""/api/v1/vision — AI Property Vision (signed-in, owner-private concepts)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth.deps import Principal, require_permission
from app.core.errors import NotFoundError
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.policies import can_view_private_property
from app.properties.service import get_property_or_404
from app.rbac.catalog import Permission
from app.storage import StorageError, get_storage
from app.vision import service

router = APIRouter(tags=["vision"])

_use = require_permission(Permission.AI_USE)


@router.post(
    "/vision/concepts",
    response_model=service.ConceptOut,
    status_code=201,
    dependencies=[Depends(rate_limit("vision", limit=10, window=3600))],
)
def create_concept(
    body: service.ConceptIn,
    principal: Principal = Depends(_use),
    db: Session = Depends(get_db),
) -> service.ConceptOut:
    """Two labelled images from a brief: the concept on its plot and the street view."""
    if body.property_id is not None:
        prop = get_property_or_404(db, body.property_id)
        if not (
            prop.is_public
            or can_view_private_property(
                db,
                principal,
                lister_id=prop.lister_id,
                agency_id=prop.agency_id,
                agent_id=prop.agent_id,
            )
        ):
            raise NotFoundError("Property not found", code="PROPERTY_NOT_FOUND")
    return service.create_concept(db, principal, body)


@router.get("/vision/concepts", response_model=list[service.ConceptOut])
def my_concepts(
    principal: Principal = Depends(_use), db: Session = Depends(get_db)
) -> list[service.ConceptOut]:
    return service.list_mine(db, principal)


@router.get("/vision/concepts/{concept_id}", response_model=service.ConceptOut)
def get_concept(
    concept_id: uuid.UUID, principal: Principal = Depends(_use), db: Session = Depends(get_db)
) -> service.ConceptOut:
    return service.concept_out(service.get_owned(db, principal, concept_id))


@router.get("/vision/concepts/{concept_id}/image", response_class=Response)
def concept_image(
    concept_id: uuid.UUID,
    variant: str = Query(default="concept", pattern="^(concept|vision)$"),
    principal: Principal = Depends(_use),
    db: Session = Depends(get_db),
) -> Response:
    row = service.get_owned(db, principal, concept_id)
    key = row.concept_key if variant == "concept" else row.vision_key
    try:
        body = get_storage().get(key)
    except StorageError as exc:
        raise NotFoundError("Image not found", code="CONCEPT_NOT_FOUND") from exc
    return Response(
        content=body,
        media_type="image/png",
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="ai-concept-{variant}.png"',
        },
    )
