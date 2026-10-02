"""/api/v1/users (self-service) and /api/v1/admin/users (administration)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.auth.deps import Principal, get_principal, require_permission
from app.auth.schemas import UserOut, user_out
from app.core.errors import ConflictError
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_db
from app.rbac.catalog import Permission, Role
from app.users import service
from app.users.models import User, UserStatus
from app.users.schemas import AdminUserOut, ProfileUpdateIn, SuspendIn

router = APIRouter(tags=["users"])


def admin_user_out(user: User) -> AdminUserOut:
    return AdminUserOut(
        **user_out(user).model_dump(),
        last_login_at=user.last_login_at,
        suspension_reason=user.suspension_reason,
    )


@router.patch("/users/me", response_model=UserOut)
def update_profile(
    body: ProfileUpdateIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> UserOut:
    user = principal.user
    changes = body.model_dump(exclude_unset=True)
    if changes.get("full_name"):
        user.full_name = " ".join(changes["full_name"].split())
    if changes.get("preferred_locale"):
        user.preferred_locale = changes["preferred_locale"]
    if "phone" in changes and changes["phone"] != user.phone:
        user.phone = changes["phone"]
        user.phone_verified_at = None  # a new number must be verified again
    audit.record(
        db,
        "user.profile_updated",
        actor_id=user.id,
        resource_type="user",
        resource_id=user.id,
        data={"fields": ",".join(sorted(changes))},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Phone number already registered", code="PHONE_TAKEN") from exc
    return user_out(user)


@router.get("/admin/users", response_model=Page[AdminUserOut])
def admin_list_users(
    q: str | None = Query(default=None, max_length=100),
    role: Role | None = None,
    status: UserStatus | None = None,
    params: PageParams = Depends(page_params),
    _: Principal = Depends(require_permission(Permission.USERS_READ)),
    db: Session = Depends(get_db),
) -> Page[AdminUserOut]:
    rows, total = service.list_users(db, params, q=q, role=role, status=status)
    return Page(
        items=[admin_user_out(u) for u in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/admin/users/{user_id}", response_model=AdminUserOut)
def admin_get_user(
    user_id: uuid.UUID,
    _: Principal = Depends(require_permission(Permission.USERS_READ)),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    return admin_user_out(service.get_user_or_404(db, user_id))


@router.post("/admin/users/{user_id}/suspend", response_model=AdminUserOut)
def admin_suspend_user(
    user_id: uuid.UUID,
    body: SuspendIn,
    actor: Principal = Depends(require_permission(Permission.USERS_SUSPEND)),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    target = service.get_user_or_404(db, user_id)
    return admin_user_out(service.suspend_user(db, actor, target, body.reason))


@router.post("/admin/users/{user_id}/reactivate", response_model=AdminUserOut)
def admin_reactivate_user(
    user_id: uuid.UUID,
    actor: Principal = Depends(require_permission(Permission.USERS_SUSPEND)),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    target = service.get_user_or_404(db, user_id)
    return admin_user_out(service.reactivate_user(db, actor, target))


@router.put("/admin/users/{user_id}/roles/{role}", response_model=AdminUserOut)
def admin_grant_role(
    user_id: uuid.UUID,
    role: Role,
    actor: Principal = Depends(require_permission(Permission.ROLES_ASSIGN)),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    target = service.get_user_or_404(db, user_id)
    return admin_user_out(service.grant_role(db, actor, target, role))


@router.delete("/admin/users/{user_id}/roles/{role}", response_model=AdminUserOut)
def admin_revoke_role(
    user_id: uuid.UUID,
    role: Role,
    actor: Principal = Depends(require_permission(Permission.ROLES_ASSIGN)),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    target = service.get_user_or_404(db, user_id)
    return admin_user_out(service.revoke_role(db, actor, target, role))
