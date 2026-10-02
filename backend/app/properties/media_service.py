"""Listing media (public images/videos) and private documents."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.auth.deps import Principal
from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.policies import can_view_private_property
from app.properties.enums import DocumentType, MediaKind, ModerationState, PropertyStatus
from app.properties.models import Property, PropertyDocument, PropertyMedia
from app.properties.service import ensure_manage, get_property_or_404
from app.properties.uploads import (
    process_image,
    safe_filename,
    sha256_hex,
    sniff_document,
    sniff_video,
)
from app.rbac.catalog import Permission
from app.storage import get_storage

_EXT = {"image/webp": "webp", "video/mp4": "mp4", "video/webm": "webm"}
_DOC_EXT = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def media_url(media: PropertyMedia, *, thumbnail: bool = False) -> str:
    suffix = "?variant=thumb" if thumbnail else ""
    return f"/api/v1/media/{media.id}{suffix}"


def _mark_changed(principal: Principal, prop: Property) -> None:
    if prop.status == PropertyStatus.APPROVED and not principal.has(Permission.PROPERTIES_MODERATE):
        prop.needs_review = True


def add_media(
    db: Session,
    principal: Principal,
    prop: Property,
    *,
    data: bytes,
    kind: MediaKind,
    caption: str | None,
) -> PropertyMedia:
    ensure_manage(db, principal, prop)
    settings = get_settings()
    count = db.execute(
        select(func.count())
        .select_from(PropertyMedia)
        .where(PropertyMedia.property_id == prop.id, PropertyMedia.deleted_at.is_(None))
    ).scalar_one()
    if count >= settings.max_media_per_property:
        raise AppError("Too many media files for this listing", code="MEDIA_LIMIT")
    next_order = (
        db.execute(
            select(func.max(PropertyMedia.sort_order)).where(PropertyMedia.property_id == prop.id)
        ).scalar_one()
        or 0
    ) + 1

    media_id = uuid.uuid4()
    base = f"properties/{prop.id}/{media_id}"
    storage = get_storage()
    if kind == MediaKind.VIDEO:
        content_type = sniff_video(data, limit=settings.max_video_bytes)
        key = f"{base}.{_EXT[content_type]}"
        storage.put(key, data, content_type)
        media = PropertyMedia(
            id=media_id,
            property_id=prop.id,
            kind=kind.value,
            storage_key=key,
            content_type=content_type,
            size_bytes=len(data),
            sort_order=next_order,
            caption=caption,
            sha256=sha256_hex(data),
            uploaded_by_id=principal.id,
        )
    else:
        image = process_image(data, limit=settings.max_image_bytes)
        key, thumb_key = f"{base}.webp", f"{base}-thumb.webp"
        storage.put(key, image.main, image.content_type)
        storage.put(thumb_key, image.thumbnail, image.content_type)
        media = PropertyMedia(
            id=media_id,
            property_id=prop.id,
            kind=kind.value,
            storage_key=key,
            thumbnail_key=thumb_key,
            content_type=image.content_type,
            size_bytes=len(image.main),
            width=image.width,
            height=image.height,
            sort_order=next_order,
            caption=caption,
            sha256=image.sha256,
            perceptual_hash=image.perceptual_hash,
            uploaded_by_id=principal.id,
        )
    db.add(media)
    _mark_changed(principal, prop)
    audit.record(
        db,
        "property.media_added",
        actor_id=principal.id,
        resource_type="property",
        resource_id=prop.id,
        data={"media_id": str(media.id), "kind": kind.value},
    )
    db.commit()
    db.refresh(prop)  # refresh the media collection
    return media


def _get_media(db: Session, prop: Property, media_id: uuid.UUID) -> PropertyMedia:
    media = db.get(PropertyMedia, media_id)
    if media is None or media.property_id != prop.id or media.deleted_at is not None:
        raise NotFoundError("Media not found", code="MEDIA_NOT_FOUND")
    return media


def delete_media(db: Session, principal: Principal, prop: Property, media_id: uuid.UUID) -> None:
    ensure_manage(db, principal, prop)
    media = _get_media(db, prop, media_id)
    media.deleted_at = datetime.now(UTC)
    audit.record(
        db,
        "property.media_deleted",
        actor_id=principal.id,
        resource_type="property",
        resource_id=prop.id,
        data={"media_id": str(media.id)},
    )
    db.commit()
    storage = get_storage()
    for key in (media.storage_key, media.thumbnail_key):
        if key:
            storage.delete(key)
    db.refresh(prop)


def reorder_media(
    db: Session, principal: Principal, prop: Property, media_ids: list[uuid.UUID]
) -> None:
    ensure_manage(db, principal, prop)
    current = {m.id: m for m in prop.media}
    if set(media_ids) != set(current) or len(media_ids) != len(current):
        raise AppError("The order must list every media item exactly once", code="INVALID_ORDER")
    for index, media_id in enumerate(media_ids, start=1):
        db.get(PropertyMedia, media_id).sort_order = index  # type: ignore[union-attr]
    db.commit()
    db.refresh(prop)


def moderate_media(
    db: Session, principal: Principal, media_id: uuid.UUID, state: ModerationState
) -> PropertyMedia:
    media = db.get(PropertyMedia, media_id)
    if media is None or media.deleted_at is not None:
        raise NotFoundError("Media not found", code="MEDIA_NOT_FOUND")
    media.moderation = state.value
    audit.record(
        db,
        "property.media_moderated",
        actor_id=principal.id,
        resource_type="property",
        resource_id=media.property_id,
        data={"media_id": str(media.id), "state": state.value},
    )
    db.commit()
    return media


def media_for_download(
    db: Session, principal: Principal | None, media_id: uuid.UUID
) -> tuple[PropertyMedia, bool]:
    """Returns the media and whether it may be cached publicly."""
    media = db.get(PropertyMedia, media_id)
    if media is None or media.deleted_at is not None:
        raise NotFoundError("Media not found", code="MEDIA_NOT_FOUND")
    prop = db.get(Property, media.property_id)
    if prop is None:
        raise NotFoundError("Media not found", code="MEDIA_NOT_FOUND")
    public = prop.is_public and media.moderation == ModerationState.APPROVED
    if public:
        return media, True
    if prop.deleted_at is None and can_view_private_property(
        db, principal, lister_id=prop.lister_id, agency_id=prop.agency_id, agent_id=prop.agent_id
    ):
        return media, False
    raise NotFoundError("Media not found", code="MEDIA_NOT_FOUND")


# --------------------------------------------------------------------------- documents


def _ensure_private_access(db: Session, principal: Principal, prop: Property) -> None:
    if not can_view_private_property(
        db, principal, lister_id=prop.lister_id, agency_id=prop.agency_id, agent_id=prop.agent_id
    ):
        raise NotFoundError("Property not found", code="PROPERTY_NOT_FOUND")


def add_document(
    db: Session,
    principal: Principal,
    prop: Property,
    *,
    data: bytes,
    doc_type: DocumentType,
    filename: str | None,
) -> PropertyDocument:
    ensure_manage(db, principal, prop)
    content_type = sniff_document(data, limit=get_settings().max_document_bytes)
    doc_id = uuid.uuid4()
    key = f"documents/{prop.id}/{doc_id}.{_DOC_EXT[content_type]}"
    get_storage().put(key, data, content_type)
    document = PropertyDocument(
        id=doc_id,
        property_id=prop.id,
        doc_type=doc_type.value,
        storage_key=key,
        filename=safe_filename(filename, f"document.{_DOC_EXT[content_type]}"),
        content_type=content_type,
        size_bytes=len(data),
        sha256=sha256_hex(data),
        uploaded_by_id=principal.id,
    )
    db.add(document)
    audit.record(
        db,
        "property.document_uploaded",
        actor_id=principal.id,
        resource_type="property",
        resource_id=prop.id,
        data={"document_id": str(doc_id), "doc_type": doc_type.value},
    )
    db.commit()
    return document


def list_documents(db: Session, principal: Principal, prop: Property) -> list[PropertyDocument]:
    _ensure_private_access(db, principal, prop)
    return list(
        db.execute(
            select(PropertyDocument)
            .where(PropertyDocument.property_id == prop.id, PropertyDocument.deleted_at.is_(None))
            .order_by(PropertyDocument.created_at)
        ).scalars()
    )


def document_for_download(
    db: Session, principal: Principal, document_id: uuid.UUID
) -> tuple[PropertyDocument, bytes]:
    document = db.get(PropertyDocument, document_id)
    if document is None or document.deleted_at is not None:
        raise NotFoundError("Document not found", code="DOCUMENT_NOT_FOUND")
    prop = get_property_or_404(db, document.property_id)
    try:
        _ensure_private_access(db, principal, prop)
    except NotFoundError as exc:
        raise NotFoundError("Document not found", code="DOCUMENT_NOT_FOUND") from exc
    audit.record(
        db,
        "property.document_downloaded",
        actor_id=principal.id,
        resource_type="property",
        resource_id=prop.id,
        data={"document_id": str(document.id)},
    )
    db.commit()
    return document, get_storage().get(document.storage_key)


def delete_document(
    db: Session, principal: Principal, prop: Property, document_id: uuid.UUID
) -> None:
    ensure_manage(db, principal, prop)
    document = db.get(PropertyDocument, document_id)
    if document is None or document.property_id != prop.id or document.deleted_at is not None:
        raise NotFoundError("Document not found", code="DOCUMENT_NOT_FOUND")
    if (
        not principal.has(Permission.PROPERTIES_MANAGE_ANY)
        and principal.id != document.uploaded_by_id
    ):
        raise PermissionDeniedError("Only the uploader can delete this document")
    document.deleted_at = datetime.now(UTC)
    audit.record(
        db,
        "property.document_deleted",
        actor_id=principal.id,
        resource_type="property",
        resource_id=prop.id,
        data={"document_id": str(document.id)},
    )
    db.commit()
    get_storage().delete(document.storage_key)
