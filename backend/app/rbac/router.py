"""/api/v1/rbac (catalog) and /api/v1/admin/audit-logs."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.auth.deps import Principal, get_principal, require_permission
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_db
from app.rbac.catalog import ROLE_NAMES, ROLE_PERMISSIONS, ROLE_RANK, Permission, Role
from app.users.schemas import AuditLogOut, RoleOut

router = APIRouter(tags=["rbac"])


@router.get("/rbac/roles", response_model=list[RoleOut])
def list_roles(_: Principal = Depends(get_principal)) -> list[RoleOut]:
    return [
        RoleOut(
            code=role,
            name_ar=ROLE_NAMES[role][0],
            name_en=ROLE_NAMES[role][1],
            rank=ROLE_RANK[role],
            permissions=sorted(p.value for p in ROLE_PERMISSIONS[role]),
        )
        for role in sorted(Role, key=lambda r: -ROLE_RANK[r])
    ]


@router.get("/admin/audit-logs", response_model=Page[AuditLogOut])
def list_audit_logs(
    action: str | None = Query(default=None, max_length=100),
    actor_user_id: uuid.UUID | None = None,
    resource_type: str | None = Query(default=None, max_length=50),
    resource_id: str | None = Query(default=None, max_length=64),
    since: datetime | None = None,
    until: datetime | None = None,
    params: PageParams = Depends(page_params),
    _: Principal = Depends(require_permission(Permission.AUDIT_READ)),
    db: Session = Depends(get_db),
) -> Page[AuditLogOut]:
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if resource_id:
        stmt = stmt.where(AuditLog.resource_id == resource_id)
    if since:
        stmt = stmt.where(AuditLog.occurred_at >= since)
    if until:
        stmt = stmt.where(AuditLog.occurred_at < until)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(AuditLog.occurred_at.desc()).offset(params.offset).limit(params.page_size)
    ).scalars()
    return Page(
        items=[AuditLogOut.model_validate(r) for r in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )
