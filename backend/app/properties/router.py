"""/api/v1/properties, /api/v1/me/properties, /api/v1/media, /api/v1/documents."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth.deps import (
    Principal,
    get_optional_principal,
    get_principal,
    require_permission,
    require_verified_email,
)
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_db
from app.policies import can_view_private_property
from app.properties import media_service, service
from app.properties.enums import DocumentType, MediaKind, ModerationState, PropertyStatus
from app.properties.models import Property, PropertyMedia, PropertyVerification
from app.properties.presenter import to_cards, to_out
from app.properties.schemas import (
    DocumentOut,
    MediaOrderIn,
    MediaOut,
    ModerationIn,
    PriceHistoryOut,
    PropertyCard,
    PropertyCreate,
    PropertyOut,
    PropertyUpdate,
    StatusChangeIn,
    StatusHistoryOut,
    VerificationIn,
    VerificationOut,
)
from app.rbac.catalog import Permission
from app.storage import StorageError, get_storage

router = APIRouter(tags=["properties"])


async def read_upload(upload: UploadFile, limit: int) -> bytes:
    """Read at most ``limit + 1`` bytes so oversized uploads are rejected cheaply."""
    data = await upload.read(limit + 1)
    await upload.close()
    return data


def _visible(db: Session, principal: Principal | None, property_id: uuid.UUID) -> Property:
    prop = service.get_property_or_404(db, property_id)
    if prop.is_public or can_view_private_property(
        db, principal, lister_id=prop.lister_id, agency_id=prop.agency_id, agent_id=prop.agent_id
    ):
        return prop
    raise NotFoundError("Property not found", code="PROPERTY_NOT_FOUND")


# --------------------------------------------------------------------------- CRUD


@router.post("/properties", response_model=PropertyOut, status_code=status.HTTP_201_CREATED)
def create_property(
    body: PropertyCreate,
    principal: Principal = Depends(require_verified_email),
    _: Principal = Depends(require_permission(Permission.PROPERTIES_CREATE)),
    db: Session = Depends(get_db),
) -> PropertyOut:
    return to_out(db, service.create_property(db, principal, body), principal)


@router.get("/properties", response_model=Page[PropertyCard])
def list_properties(
    params: PageParams = Depends(page_params), db: Session = Depends(get_db)
) -> Page[PropertyCard]:
    rows, total = service.list_public(db, offset=params.offset, limit=params.page_size)
    return Page(items=to_cards(db, rows), total=total, page=params.page, page_size=params.page_size)


@router.get("/me/properties", response_model=Page[PropertyCard])
def my_properties(
    status_filter: PropertyStatus | None = Query(default=None, alias="status"),
    params: PageParams = Depends(page_params),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> Page[PropertyCard]:
    rows, total = service.list_managed(
        db,
        principal,
        status=status_filter.value if status_filter else None,
        offset=params.offset,
        limit=params.page_size,
    )
    return Page(items=to_cards(db, rows), total=total, page=params.page, page_size=params.page_size)


@router.get("/properties/{property_id}", response_model=PropertyOut)
def get_property(
    property_id: uuid.UUID,
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> PropertyOut:
    return to_out(db, _visible(db, principal, property_id), principal)


@router.patch("/properties/{property_id}", response_model=PropertyOut)
def update_property(
    property_id: uuid.UUID,
    body: PropertyUpdate,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> PropertyOut:
    prop = service.get_property_or_404(db, property_id, lock=True)
    return to_out(db, service.update_property(db, principal, prop, body), principal)


@router.delete("/properties/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property(
    property_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> None:
    service.delete_property(db, principal, service.get_property_or_404(db, property_id))


# --------------------------------------------------------------------------- lifecycle


def _transition(action: str) -> Callable[..., PropertyOut]:
    def endpoint(
        property_id: uuid.UUID,
        body: StatusChangeIn | None = None,
        principal: Principal = Depends(get_principal),
        db: Session = Depends(get_db),
    ) -> PropertyOut:
        prop = service.get_property_or_404(db, property_id, lock=True)
        reason = body.reason if body else None
        return to_out(db, service.owner_transition(db, principal, prop, action, reason), principal)

    return endpoint


for _action, _path in [
    ("submit", "submit"),
    ("unpublish", "unpublish"),
    ("archive", "archive"),
    ("mark_sold", "mark-sold"),
    ("mark_rented", "mark-rented"),
]:
    router.add_api_route(
        f"/properties/{{property_id}}/{_path}",
        _transition(_action),
        methods=["POST"],
        response_model=PropertyOut,
        name=f"property_{_action}",
    )


@router.post("/properties/{property_id}/moderate", response_model=PropertyOut)
def moderate_property(
    property_id: uuid.UUID,
    body: ModerationIn,
    principal: Principal = Depends(require_permission(Permission.PROPERTIES_MODERATE)),
    db: Session = Depends(get_db),
) -> PropertyOut:
    prop = service.get_property_or_404(db, property_id, lock=True)
    return to_out(db, service.moderate(db, principal, prop, body.decision, body.reason), principal)


@router.post(
    "/properties/{property_id}/verifications",
    response_model=VerificationOut,
    status_code=status.HTTP_201_CREATED,
)
def add_verification(
    property_id: uuid.UUID,
    body: VerificationIn,
    principal: Principal = Depends(require_permission(Permission.PROPERTIES_VERIFY)),
    db: Session = Depends(get_db),
) -> VerificationOut:
    prop = service.get_property_or_404(db, property_id)
    return VerificationOut.model_validate(service.add_verification(db, principal, prop, body))


@router.get("/properties/{property_id}/verifications", response_model=list[VerificationOut])
def list_verifications(
    property_id: uuid.UUID,
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> list[VerificationOut]:
    """Transparent verification: what was checked and the outcome (not private notes)."""
    prop = _visible(db, principal, property_id)
    private = can_view_private_property(
        db, principal, lister_id=prop.lister_id, agency_id=prop.agency_id, agent_id=prop.agent_id
    )
    rows = db.execute(
        select(PropertyVerification)
        .where(PropertyVerification.property_id == prop.id)
        .order_by(PropertyVerification.created_at)
    ).scalars()
    result = []
    for row in rows:
        out = VerificationOut.model_validate(row)
        if not private:
            out.note = None
        result.append(out)
    return result


@router.get("/properties/{property_id}/price-history", response_model=list[PriceHistoryOut])
def get_price_history(
    property_id: uuid.UUID,
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> list[PriceHistoryOut]:
    prop = _visible(db, principal, property_id)
    return [
        PriceHistoryOut(
            price_amount=h.price_amount,
            currency=h.currency,
            price_on_request=h.price_on_request,
            changed_at=h.changed_at,
        )
        for h in service.price_history(db, prop)
    ]


@router.get("/properties/{property_id}/status-history", response_model=list[StatusHistoryOut])
def get_status_history(
    property_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> list[StatusHistoryOut]:
    prop = service.get_property_or_404(db, property_id)
    if not can_view_private_property(
        db, principal, lister_id=prop.lister_id, agency_id=prop.agency_id, agent_id=prop.agent_id
    ):
        raise NotFoundError("Property not found", code="PROPERTY_NOT_FOUND")
    return [
        StatusHistoryOut(
            from_status=h.from_status,
            to_status=h.to_status,
            reason=h.reason,
            changed_at=h.changed_at,
        )
        for h in service.status_history(db, prop)
    ]


# --------------------------------------------------------------------------- media


@router.post(
    "/properties/{property_id}/media", response_model=MediaOut, status_code=status.HTTP_201_CREATED
)
async def upload_media(
    property_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    kind: Annotated[MediaKind, Form()] = MediaKind.IMAGE,
    caption: Annotated[str | None, Form(max_length=200)] = None,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> MediaOut:
    settings = get_settings()
    limit = settings.max_video_bytes if kind == MediaKind.VIDEO else settings.max_image_bytes
    data = await read_upload(file, limit)

    def store() -> PropertyMedia:  # blocking DB + image work off the event loop
        prop = service.get_property_or_404(db, property_id)
        return media_service.add_media(db, principal, prop, data=data, kind=kind, caption=caption)

    media = await run_in_threadpool(store)
    out = MediaOut.model_validate(media)
    out.url = media_service.media_url(media)
    out.thumbnail_url = (
        media_service.media_url(media, thumbnail=True) if media.thumbnail_key else None
    )
    return out


@router.put("/properties/{property_id}/media/order", status_code=status.HTTP_204_NO_CONTENT)
def reorder_media(
    property_id: uuid.UUID,
    body: MediaOrderIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> None:
    prop = service.get_property_or_404(db, property_id)
    media_service.reorder_media(db, principal, prop, body.media_ids)


@router.delete("/properties/{property_id}/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_media(
    property_id: uuid.UUID,
    media_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> None:
    prop = service.get_property_or_404(db, property_id)
    media_service.delete_media(db, principal, prop, media_id)


@router.post("/media/{media_id}/moderate", response_model=MediaOut)
def moderate_media(
    media_id: uuid.UUID,
    state: ModerationState,
    principal: Principal = Depends(require_permission(Permission.PROPERTIES_MODERATE)),
    db: Session = Depends(get_db),
) -> MediaOut:
    media = media_service.moderate_media(db, principal, media_id, state)
    out = MediaOut.model_validate(media)
    out.url = media_service.media_url(media)
    return out


@router.get("/media/{media_id}", response_class=Response)
def get_media(
    media_id: uuid.UUID,
    request: Request,
    variant: str = Query(default="full", pattern="^(full|thumb)$"),
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> Response:
    media, public = media_service.media_for_download(db, principal, media_id)
    key = media.thumbnail_key if variant == "thumb" and media.thumbnail_key else media.storage_key
    etag = f'"{media.sha256[:32]}-{variant}"'
    cache = "public, max-age=86400" if public else "private, no-store"
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": cache})
    try:
        body = get_storage().get(key)
    except StorageError as exc:
        raise NotFoundError("Media not found", code="MEDIA_NOT_FOUND") from exc
    return Response(
        content=body,
        media_type=media.content_type,
        headers={
            "Cache-Control": cache,
            "ETag": etag,
            # Served from the API origin: never let a browser sniff it into HTML.
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


# --------------------------------------------------------------------------- documents


@router.post(
    "/properties/{property_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    property_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    doc_type: Annotated[DocumentType, Form()] = DocumentType.OTHER,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> DocumentOut:
    data = await read_upload(file, get_settings().max_document_bytes)

    def store() -> DocumentOut:
        prop = service.get_property_or_404(db, property_id)
        document = media_service.add_document(
            db, principal, prop, data=data, doc_type=doc_type, filename=file.filename
        )
        return DocumentOut.model_validate(document)

    return await run_in_threadpool(store)


@router.get("/properties/{property_id}/documents", response_model=list[DocumentOut])
def list_documents(
    property_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> list[DocumentOut]:
    prop = service.get_property_or_404(db, property_id)
    return [
        DocumentOut.model_validate(d) for d in media_service.list_documents(db, principal, prop)
    ]


@router.get("/documents/{document_id}", response_class=Response)
def download_document(
    document_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> Response:
    document, body = media_service.document_for_download(db, principal, document_id)
    return Response(
        content=body,
        media_type=document.content_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'attachment; filename="document-{document.id}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.delete(
    "/properties/{property_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_document(
    property_id: uuid.UUID,
    document_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> None:
    prop = service.get_property_or_404(db, property_id)
    media_service.delete_document(db, principal, prop, document_id)
