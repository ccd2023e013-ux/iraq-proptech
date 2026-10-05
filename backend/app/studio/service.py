"""Property Media Studio: storyboards from listing data, and render outputs.

The storyboard is the pipeline's contract: the server decides *what* the video
says (only listing facts, the listing's approved photos, recorded nearby
places with their sources, and the DEMO flag); a renderer decides *how* it
looks. The default renderer runs in the user's browser (canvas + MediaRecorder),
so the free deployment never encodes video. Server/external renderers plug in
behind the same storyboard later.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from geoalchemy2 import Geography
from pydantic import BaseModel, ConfigDict
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.auth.deps import Principal
from app.core.errors import AppError, NotFoundError
from app.geo.models import City, District
from app.geo.pois import PointOfInterest
from app.geo.spatial import point_lonlat
from app.properties.enums import MediaKind, ModerationState
from app.properties.media_service import media_url
from app.properties.models import Property, PropertyType
from app.properties.service import ensure_manage, get_property_or_404
from app.storage import get_storage
from app.studio.models import JobStatus, MediaJob, Renderer

MAX_PHOTOS = 6
MAX_OUTPUT_BYTES = 40 * 1024 * 1024
MAX_DURATION_MS = 180_000
ACCEPTED_TYPES = {"video/webm": "webm", "video/mp4": "mp4"}
NEARBY_CATEGORIES = ("SCHOOL", "HOSPITAL", "MOSQUE", "MARKET", "PARK", "UNIVERSITY", "MALL")


class JobIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_id: uuid.UUID
    format: Literal["landscape", "vertical"] = "landscape"


class JobOut(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    format: str
    renderer: str
    status: str
    storyboard: dict[str, Any]
    video_url: str | None
    output_type: str | None
    output_bytes: int | None
    duration_ms: int | None


def _out(job: MediaJob) -> JobOut:
    return JobOut(
        id=job.id,
        property_id=job.property_id,
        format=job.format,
        renderer=job.renderer,
        status=job.status,
        storyboard=job.storyboard,
        video_url=f"/api/v1/studio/jobs/{job.id}/video" if job.output_key else None,
        output_type=job.output_type,
        output_bytes=job.output_bytes,
        duration_ms=job.duration_ms,
    )


def _nearby(db: Session, prop: Property) -> list[dict[str, Any]]:
    if prop.display_location is None:
        return []
    geog = Geography(geometry_type="POINT", srid=4326)
    centre = cast(
        select(Property.display_location).where(Property.id == prop.id).scalar_subquery(), geog
    )
    poi = cast(PointOfInterest.location, geog)
    distance = func.ST_Distance(poi, centre)
    rows = db.execute(
        select(PointOfInterest, distance)
        .where(
            PointOfInterest.is_active.is_(True),
            PointOfInterest.category.in_(NEARBY_CATEGORIES),
            func.ST_DWithin(poi, centre, 2000),
        )
        .order_by(PointOfInterest.is_demo, distance)
        .limit(200)
    ).all()
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for place, dist in rows:
        if place.category in seen:
            continue
        seen.add(place.category)
        out.append(
            {
                "category": place.category,
                "name_ar": place.name_ar,
                "name_en": place.name_en,
                "distance_m": int(round(float(dist), -1)),
                "source": place.source,
                "is_demo": place.is_demo,
            }
        )
    return out[:4]


def build_storyboard(db: Session, prop: Property, fmt: str) -> dict[str, Any]:
    ptype = db.get(PropertyType, prop.property_type_code)
    city = db.get(City, prop.city_id)
    district = db.get(District, prop.district_id) if prop.district_id else None
    lonlat = point_lonlat(prop.display_location) if prop.display_location is not None else None
    if lonlat is None and city is not None and city.centroid is not None:
        lonlat = point_lonlat(city.centroid)
    photos = [
        media_url(m)
        for m in prop.media
        if m.kind == MediaKind.IMAGE and m.moderation == ModerationState.APPROVED
    ][:MAX_PHOTOS]
    nearby = _nearby(db, prop)
    scenes: list[dict[str, Any]] = [
        {
            "type": "map_intro",
            "duration_ms": 3500,
            "lon": lonlat[0] if lonlat else None,
            "lat": lonlat[1] if lonlat else None,
            "approximate": prop.location_privacy != "EXACT",
        }
    ]
    scenes += [{"type": "photo", "duration_ms": 3000, "url": url} for url in photos]
    scenes.append({"type": "facts", "duration_ms": 4000})
    if nearby:
        scenes.append({"type": "nearby", "duration_ms": 4000, "items": nearby})
    scenes.append({"type": "cta", "duration_ms": 3500})
    return {
        "version": 1,
        "format": fmt,
        "size": [1920, 1080] if fmt == "landscape" else [1080, 1920],
        "fps": 30,
        "is_demo": prop.is_demo,
        "property": {
            "id": str(prop.id),
            "reference_code": prop.reference_code,
            "path": f"/properties/{prop.id}",
            "title_ar": prop.title_ar,
            "title_en": prop.title_en,
            "type_ar": ptype.name_ar if ptype else prop.property_type_code,
            "type_en": ptype.name_en if ptype else prop.property_type_code,
            "purpose": prop.purpose,
            "city_ar": city.name_ar if city else None,
            "city_en": city.name_en if city else None,
            "district_ar": district.name_ar if district else None,
            "district_en": district.name_en if district else None,
            "price_amount": None
            if prop.price_on_request or prop.price_amount is None
            else str(int(prop.price_amount)),
            "currency": prop.currency,
            "rent_period": prop.rent_period,
            "area_m2": str(int(prop.area_m2)) if prop.area_m2 else None,
            "bedrooms": prop.bedrooms,
            "bathrooms": prop.bathrooms,
            "verified": prop.verified_at is not None,
        },
        "scenes": scenes,
        "notes": [
            "Only listing facts, approved photos and recorded places are used.",
            "Map intro and overlays are illustrative, not geo-registered survey graphics.",
        ],
    }


def create_job(db: Session, principal: Principal, body: JobIn) -> JobOut:
    prop = get_property_or_404(db, body.property_id)
    ensure_manage(db, principal, prop)
    job = MediaJob(
        user_id=principal.id,
        property_id=prop.id,
        format=body.format,
        renderer=Renderer.BROWSER.value,
        status=JobStatus.STORYBOARD_READY.value,
        storyboard=build_storyboard(db, prop, body.format),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _out(job)


def _owned(db: Session, principal: Principal, job_id: uuid.UUID) -> MediaJob:
    job = db.get(MediaJob, job_id)
    if job is None or job.user_id != principal.id:
        raise NotFoundError("Job not found", code="JOB_NOT_FOUND")
    return job


def get_job(db: Session, principal: Principal, job_id: uuid.UUID) -> JobOut:
    return _out(_owned(db, principal, job_id))


def list_jobs(
    db: Session, principal: Principal, property_id: uuid.UUID | None = None
) -> list[JobOut]:
    stmt = select(MediaJob).where(MediaJob.user_id == principal.id)
    if property_id:
        stmt = stmt.where(MediaJob.property_id == property_id)
    rows = db.execute(stmt.order_by(MediaJob.created_at.desc()).limit(30)).scalars()
    return [_out(j) for j in rows]


def sniff_video(data: bytes) -> str | None:
    """Content type from magic bytes (never trust the client's header alone)."""
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "video/webm"
    if len(data) > 12 and data[4:8] == b"ftyp":
        return "video/mp4"
    return None


def save_output(
    db: Session,
    principal: Principal,
    job_id: uuid.UUID,
    data: bytes,
    declared_type: str,
    duration_ms: int | None,
) -> JobOut:
    job = _owned(db, principal, job_id)
    base_type = declared_type.split(";")[0].strip().lower()
    if base_type not in ACCEPTED_TYPES:
        raise AppError("Only WebM or MP4 video", code="UNSUPPORTED_MEDIA_TYPE", status_code=415)
    if len(data) < 1024 or len(data) > MAX_OUTPUT_BYTES:
        raise AppError("Video size out of range", code="FILE_TOO_LARGE", status_code=413)
    sniffed = sniff_video(data)
    if sniffed != base_type:
        raise AppError("File content does not match its type", code="INVALID_FILE", status_code=422)
    if duration_ms is not None and not (0 < duration_ms <= MAX_DURATION_MS):
        raise AppError("Invalid duration", code="VALIDATION_ERROR", status_code=422)
    key = f"studio/{job.id}/video.{ACCEPTED_TYPES[base_type]}"
    get_storage().put(key, data, base_type)
    job.output_key, job.output_type, job.output_bytes = key, base_type, len(data)
    job.duration_ms = duration_ms
    job.status = JobStatus.DONE.value
    db.commit()
    db.refresh(job)
    return _out(job)


def video_bytes(db: Session, principal: Principal, job_id: uuid.UUID) -> tuple[bytes, str]:
    job = _owned(db, principal, job_id)
    if not job.output_key or not job.output_type:
        raise NotFoundError("No video yet", code="JOB_NOT_FOUND")
    return get_storage().get(job.output_key), job.output_type
