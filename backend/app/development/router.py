"""/api/v1/development — "Future Iraq": projects with their sources (public, read-only).

Only published projects with evidence are served. Responses always carry the
provenance (organisation, URL, publication date, retrieval date) so clients
can never show a project without saying where it comes from.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.auth.deps import Principal, require_permission
from app.core.errors import AppError, NotFoundError
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.development import service
from app.development.models import DevelopmentSource, ProjectCategory
from app.rbac.catalog import Permission

router = APIRouter(
    tags=["development"],
    dependencies=[Depends(rate_limit("development", limit=120, window=60))],
)
CACHE = "public, max-age=300"


def _bbox(value: str | None) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    try:
        west, south, east, north = (float(v) for v in value.split(","))
    except ValueError as exc:
        raise AppError("bbox must be 'west,south,east,north'", code="VALIDATION_ERROR") from exc
    if west >= east or south >= north:
        raise AppError("Invalid bbox", code="VALIDATION_ERROR", status_code=422)
    return west, south, east, north


@router.get("/development/projects")
def development_projects(
    response: Response,
    bbox: str | None = Query(default=None, max_length=120),
    category: list[ProjectCategory] | None = Query(default=None),
    evidence: bool = Query(default=False, description="Include each project's evidence"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """GeoJSON of published projects; every feature carries status, confidence and sources."""
    rows = service.list_projects(
        db, bbox=_bbox(bbox), categories=[c.value for c in category] if category else None
    )
    response.headers["Cache-Control"] = CACHE
    features = []
    for p in rows:
        props = service.project_out(p, with_evidence=evidence)
        lon, lat = props.pop("lon"), props.pop("lat")
        features.append(
            {
                "type": "Feature",
                "id": props["id"],
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": props,
            }
        )
    return {
        "type": "FeatureCollection",
        "features": features,
        "meta": {
            "count": len(features),
            "basis": "published sources only; see each project's evidence",
        },
    }


@router.get("/development/projects/{project_id}")
def development_project(
    project_id: uuid.UUID, response: Response, db: Session = Depends(get_db)
) -> dict[str, Any]:
    project = service.get_project(db, project_id)
    if project is None:
        raise NotFoundError("Project not found", code="PROJECT_NOT_FOUND")
    response.headers["Cache-Control"] = CACHE
    return service.project_out(project)


@router.get("/development/sources")
def development_sources(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.execute(select(DevelopmentSource).order_by(DevelopmentSource.name)).scalars()
    return [
        {
            "name": s.name,
            "organization": s.organization,
            "url": s.url,
            "kind": s.kind,
            "terms_note": s.terms_note,
        }
        for s in rows
    ]


@router.post("/admin/development/import")
def import_development(
    dataset: str = Query("basra", pattern="^[a-z]+$"),
    principal: Principal = Depends(require_permission(Permission.DEVELOPMENT_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Load a curated, source-cited dataset shipped with the code (idempotent)."""
    if dataset not in service.DATASETS:
        raise NotFoundError("Unknown dataset", code="DATASET_NOT_FOUND")
    result = service.import_dataset(db, dataset)
    audit.record(
        db,
        "development.import",
        actor_id=principal.id,
        resource_type="development_dataset",
        resource_id=dataset,
        data=result,
    )
    db.commit()
    return result
