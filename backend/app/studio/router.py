"""/api/v1/studio — Property Media Studio (listing managers only)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.auth.deps import Principal, require_permission
from app.core.errors import AppError, NotFoundError
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.rbac.catalog import Permission
from app.storage import StorageError
from app.studio import service

router = APIRouter(tags=["studio"])
_lister = require_permission(Permission.PROPERTIES_CREATE)


@router.post(
    "/studio/jobs",
    response_model=service.JobOut,
    status_code=201,
    dependencies=[Depends(rate_limit("studio", limit=30, window=3600))],
)
def create_job(
    body: service.JobIn, principal: Principal = Depends(_lister), db: Session = Depends(get_db)
) -> service.JobOut:
    """Storyboard for a listing you manage (rendered by the chosen renderer)."""
    return service.create_job(db, principal, body)


@router.get("/studio/jobs", response_model=list[service.JobOut])
def list_jobs(
    property_id: uuid.UUID | None = Query(default=None),
    principal: Principal = Depends(_lister),
    db: Session = Depends(get_db),
) -> list[service.JobOut]:
    return service.list_jobs(db, principal, property_id)


@router.get("/studio/jobs/{job_id}", response_model=service.JobOut)
def get_job(
    job_id: uuid.UUID, principal: Principal = Depends(_lister), db: Session = Depends(get_db)
) -> service.JobOut:
    return service.get_job(db, principal, job_id)


@router.put(
    "/studio/jobs/{job_id}/output",
    response_model=service.JobOut,
    dependencies=[Depends(rate_limit("studio-upload", limit=30, window=3600))],
)
async def upload_output(
    job_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(_lister),
    db: Session = Depends(get_db),
) -> service.JobOut:
    """The rendered video (raw body, WebM or MP4, checked by magic bytes, size-capped)."""
    declared = request.headers.get("content-type", "")
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > service.MAX_OUTPUT_BYTES:
        raise AppError("Video too large", code="FILE_TOO_LARGE", status_code=413)
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > service.MAX_OUTPUT_BYTES:
            raise AppError("Video too large", code="FILE_TOO_LARGE", status_code=413)
        chunks.append(chunk)
    duration_header = request.headers.get("x-duration-ms", "")
    duration = int(duration_header) if duration_header.isdigit() else None
    return service.save_output(db, principal, job_id, b"".join(chunks), declared, duration)


@router.get("/studio/jobs/{job_id}/video", response_class=Response)
def job_video(
    job_id: uuid.UUID, principal: Principal = Depends(_lister), db: Session = Depends(get_db)
) -> Response:
    try:
        data, content_type = service.video_bytes(db, principal, job_id)
    except StorageError as exc:
        raise NotFoundError("Video not found", code="JOB_NOT_FOUND") from exc
    ext = "mp4" if content_type == "video/mp4" else "webm"
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="property-video.{ext}"',
        },
    )
