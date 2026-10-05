"""Development Intelligence: curated imports, provenance rules and queries."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.development.models import (
    Confidence,
    DevelopmentEvidence,
    DevelopmentProject,
    DevelopmentSource,
    EvidenceSupports,
    LocationPrecision,
    ProjectCategory,
    ProjectStatus,
    SourceKind,
)
from app.geo.manage import IRAQ_LAT, IRAQ_LON
from app.geo.models import Governorate
from app.geo.spatial import make_point, point_lonlat

DATA_DIR = Path(__file__).parent / "data"
DATASETS = {"basra": ("basra.json", "BSR")}


class ProvenanceError(ValueError):
    """A record without the evidence that makes it publishable."""


def check_url(url: str) -> str:
    """Stored only (never fetched by the server): must be an absolute https URL."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or len(url) > 500:
        raise ProvenanceError(f"evidence URL must be an absolute https URL: {url!r}")
    return url


def validate_project(record: dict[str, Any]) -> None:
    """Rules every curated or admin-entered project must satisfy."""
    if record["category"] not in ProjectCategory.__members__:
        raise ProvenanceError(f"unknown category {record['category']}")
    if record["status"] not in ProjectStatus.__members__:
        raise ProvenanceError(f"unknown status {record['status']}")
    if record["location_precision"] not in LocationPrecision.__members__:
        raise ProvenanceError("unknown location precision")
    if record["confidence"] not in Confidence.__members__:
        raise ProvenanceError("unknown confidence")
    lon, lat = float(record["lon"]), float(record["lat"])
    if not (IRAQ_LON[0] <= lon <= IRAQ_LON[1] and IRAQ_LAT[0] <= lat <= IRAQ_LAT[1]):
        raise ProvenanceError("location outside Iraq")
    if record["location_precision"] != "EXACT" and not record.get("location_note"):
        raise ProvenanceError("approximate locations need a location_note")
    evidence = record.get("evidence") or []
    if not evidence:
        raise ProvenanceError(f"{record['slug']}: at least one evidence item is required")
    for item in evidence:
        check_url(item["url"])
        if item["supports"] not in EvidenceSupports.__members__:
            raise ProvenanceError("unknown evidence type")
    # A stated timeline needs evidence for it (or for the status it belongs to).
    if (record.get("timeline_en") or record.get("target_year")) and not any(
        e["supports"] in ("TIMELINE", "STATUS") for e in evidence
    ):
        raise ProvenanceError(f"{record['slug']}: a timeline needs TIMELINE/STATUS evidence")


def import_dataset(db: Session, name: str = "basra") -> dict[str, Any]:
    """Idempotent import of a curated dataset (upsert by source URL and project slug)."""
    filename, gov_code = DATASETS[name]
    data = json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))
    gov = db.execute(select(Governorate).where(Governorate.code == gov_code)).scalar_one_or_none()
    now = datetime.now(UTC)

    sources: dict[str, DevelopmentSource] = {}
    for s in data["sources"]:
        if s["kind"] not in SourceKind.__members__:
            raise ProvenanceError(f"unknown source kind {s['kind']}")
        check_url(s["url"])
        source = db.execute(
            select(DevelopmentSource).where(DevelopmentSource.url == s["url"])
        ).scalar_one_or_none()
        if source is None:
            source = DevelopmentSource(url=s["url"])
            db.add(source)
        source.name, source.organization, source.kind = s["name"], s["organization"], s["kind"]
        source.terms_note = s.get("terms_note")
        sources[s["key"]] = source
    db.flush()

    created = updated = 0
    for p in data["projects"]:
        validate_project(p)
        row = db.execute(
            select(DevelopmentProject).where(DevelopmentProject.slug == p["slug"])
        ).scalar_one_or_none()
        if row is None:
            row = DevelopmentProject(slug=p["slug"], is_demo=False)
            db.add(row)
            created += 1
        else:
            updated += 1
        for field in (
            "name_ar",
            "name_en",
            "category",
            "status",
            "summary_ar",
            "summary_en",
            "location_precision",
            "location_note",
            "timeline_ar",
            "timeline_en",
            "target_year",
            "confidence",
        ):
            setattr(row, field, p.get(field))
        row.location = make_point(float(p["lon"]), float(p["lat"]))
        row.governorate_id = gov.id if gov else None
        row.is_published = True
        row.last_verified_at = now
        row.evidence = [
            DevelopmentEvidence(
                source=sources[e["source"]],
                url=e["url"],
                title=e["title"],
                published_on=date.fromisoformat(e["published_on"])
                if e.get("published_on")
                else None,
                retrieved_at=now,
                excerpt=e.get("excerpt"),
                supports=e["supports"],
            )
            for e in p["evidence"]
        ]
    db.commit()
    return {"dataset": name, "sources": len(sources), "created": created, "updated": updated}


# --- queries


def _public() -> list[Any]:
    return [DevelopmentProject.is_published.is_(True)]


def evidence_out(e: DevelopmentEvidence) -> dict[str, Any]:
    return {
        "url": e.url,
        "title": e.title,
        "published_on": e.published_on.isoformat() if e.published_on else None,
        "retrieved_at": e.retrieved_at.isoformat(),
        "excerpt": e.excerpt,
        "supports": e.supports,
        "source": {
            "name": e.source.name,
            "organization": e.source.organization,
            "kind": e.source.kind,
            "url": e.source.url,
        },
    }


def project_out(p: DevelopmentProject, *, with_evidence: bool = True) -> dict[str, Any]:
    lonlat = point_lonlat(p.location)
    newest = max((e.published_on for e in p.evidence if e.published_on), default=None)
    out: dict[str, Any] = {
        "id": str(p.id),
        "slug": p.slug,
        "name_ar": p.name_ar,
        "name_en": p.name_en,
        "category": p.category,
        "status": p.status,
        "summary_ar": p.summary_ar,
        "summary_en": p.summary_en,
        "lon": lonlat[0] if lonlat else None,
        "lat": lonlat[1] if lonlat else None,
        "location_precision": p.location_precision,
        "location_note": p.location_note,
        "timeline_ar": p.timeline_ar,
        "timeline_en": p.timeline_en,
        "target_year": p.target_year,
        "confidence": p.confidence,
        "is_demo": p.is_demo,
        "last_verified_at": p.last_verified_at.isoformat() if p.last_verified_at else None,
        "latest_source_date": newest.isoformat() if newest else None,
        "sources": sorted({e.source.organization for e in p.evidence}),
    }
    if with_evidence:
        out["evidence"] = [evidence_out(e) for e in p.evidence]
    return out


def list_projects(
    db: Session,
    *,
    bbox: tuple[float, float, float, float] | None = None,
    categories: list[str] | None = None,
) -> list[DevelopmentProject]:
    stmt = select(DevelopmentProject).where(*_public())
    if bbox:
        stmt = stmt.where(
            func.ST_Intersects(DevelopmentProject.location, func.ST_MakeEnvelope(*bbox, 4326))
        )
    if categories:
        stmt = stmt.where(DevelopmentProject.category.in_(categories))
    return list(db.execute(stmt.order_by(DevelopmentProject.name_en).limit(1000)).scalars())


def get_project(db: Session, project_id: uuid.UUID) -> DevelopmentProject | None:
    row = db.get(DevelopmentProject, project_id)
    return row if row is not None and row.is_published else None


def projects_near(
    db: Session, lon: float, lat: float, radius_m: float = 15_000, limit: int = 5
) -> list[tuple[DevelopmentProject, float]]:
    geog = Geography(geometry_type="POINT", srid=4326)
    here = cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), geog)
    where = cast(DevelopmentProject.location, geog)
    distance = func.ST_Distance(where, here)
    rows = db.execute(
        select(DevelopmentProject, distance)
        .where(*_public(), func.ST_DWithin(where, here, radius_m))
        .order_by(distance)
        .limit(limit)
    ).all()
    return [(p, float(d)) for p, d in rows]
