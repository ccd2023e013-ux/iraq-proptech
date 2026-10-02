"""Analytics API: view beacons and role-scoped dashboards."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import service
from app.auth.deps import Principal, get_optional_principal, get_principal
from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.policies import can_manage_property, is_agency_owner, membership
from app.properties.enums import PropertyStatus
from app.properties.models import Property
from app.rbac.catalog import Permission

router = APIRouter(tags=["analytics"])


def _range(date_from: date | None, date_to: date | None) -> service.Range:
    end = date_to or service.today()
    start = date_from or (end - timedelta(days=29))
    if start > end:
        raise AppError("date_from must not be after date_to", code="INVALID_RANGE")
    if (end - start).days + 1 > service.MAX_RANGE_DAYS:
        raise AppError(
            f"The range may cover at most {service.MAX_RANGE_DAYS} days", code="INVALID_RANGE"
        )
    return service.Range(start, end)


@router.post(
    "/analytics/property-views/{property_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("analytics-view", limit=300, window=3600))],
)
def property_view(
    property_id: uuid.UUID,
    request: Request,
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> None:
    """Beacon sent by the listing page. Counts unique visitors per day; owners are not counted."""
    prop = db.execute(
        select(Property).where(
            Property.id == property_id,
            Property.status == PropertyStatus.APPROVED,
            Property.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if prop is None:
        return None
    if principal is not None:
        if principal.id in (prop.lister_id, prop.agent_id):
            return None
        key = f"u:{principal.id}"
    else:
        ip = request.client.host if request.client else "unknown"
        key = f"a:{ip}:{request.headers.get('user-agent', '')[:200]}"
    service.record_view(db, prop.id, key)
    db.commit()
    return None


@router.get("/analytics/overview")
def analytics_overview(
    scope: Literal["me", "agency", "platform"] = "me",
    agency_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    include_demo: bool = False,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rng = _range(date_from, date_to)
    if scope == "platform":
        if not principal.has(Permission.ANALYTICS_ALL):
            raise PermissionDeniedError("Platform analytics require analytics.all")
        spec = service.ScopeSpec("platform", include_demo=include_demo)
    elif scope == "agency":
        if agency_id is None:
            m = membership(db, principal.id)
            agency_id = m.agency_id if m is not None else None
        if agency_id is None:
            raise NotFoundError("Agency not found")
        allowed = principal.has(Permission.ANALYTICS_ALL) or (
            principal.has(Permission.ANALYTICS_AGENCY)
            and is_agency_owner(db, principal.id, agency_id)
        )
        if not allowed:
            # Do not reveal whether the agency exists.
            raise NotFoundError("Agency not found")
        spec = service.ScopeSpec("agency", agency_id=agency_id, include_demo=include_demo)
    else:
        if not principal.has(Permission.ANALYTICS_OWN):
            raise PermissionDeniedError("Analytics are available to listers")
        spec = service.ScopeSpec("me", user_id=principal.id, include_demo=include_demo)
    return service.overview(db, spec, rng)


@router.get("/analytics/properties/{property_id}")
def property_analytics(
    property_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = Query(default=None),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rng = _range(date_from, date_to)
    prop = db.get(Property, property_id)
    if prop is None or not (
        principal.has(Permission.ANALYTICS_ALL)
        or can_manage_property(
            db,
            principal,
            lister_id=prop.lister_id,
            agency_id=prop.agency_id,
            agent_id=prop.agent_id,
        )
    ):
        raise NotFoundError("Property not found")
    return service.overview(db, service.ScopeSpec("property", property_id=prop.id), rng)
