"""User administration use cases (role hierarchy enforced here)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.auth.deps import Principal
from app.auth.service import revoke_all_sessions
from app.core.errors import AppError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.pagination import PageParams
from app.rbac.catalog import Role, can_grant, can_manage
from app.users.models import User, UserRole, UserStatus


def get_user_or_404(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise NotFoundError("User not found", code="USER_NOT_FOUND")
    return user


def _ensure_can_manage(actor: Principal, target: User) -> None:
    if actor.id == target.id:
        raise PermissionDeniedError("You cannot perform this action on your own account")
    if not can_manage(actor.roles, target.roles):
        raise PermissionDeniedError(
            "You cannot manage a user with an equal or higher role", code="ROLE_HIERARCHY"
        )


def list_users(
    db: Session,
    params: PageParams,
    *,
    q: str | None,
    role: Role | None,
    status: UserStatus | None,
) -> tuple[list[User], int]:
    stmt = select(User).where(User.deleted_at.is_(None))
    if q:
        term = q.strip().lower()
        stmt = stmt.where(
            or_(
                User.email.contains(term, autoescape=True),
                func.lower(User.full_name).contains(term, autoescape=True),
                User.phone.contains(term, autoescape=True),
            )
        )
    if role:
        stmt = stmt.where(
            User.id.in_(select(UserRole.user_id).where(UserRole.role_code == role.value))
        )
    if status:
        stmt = stmt.where(User.status == status.value)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(User.created_at.desc()).offset(params.offset).limit(params.page_size)
    ).scalars()
    return list(rows), total


def suspend_user(db: Session, actor: Principal, target: User, reason: str) -> User:
    _ensure_can_manage(actor, target)
    target.status = UserStatus.SUSPENDED
    target.suspension_reason = reason
    revoke_all_sessions(db, target.id, reason="suspended", actor_id=actor.id)
    audit.record(
        db,
        "user.suspended",
        actor_id=actor.id,
        resource_type="user",
        resource_id=target.id,
        data={"reason": reason},
    )
    db.commit()
    return target


def reactivate_user(db: Session, actor: Principal, target: User) -> User:
    _ensure_can_manage(actor, target)
    target.status = UserStatus.ACTIVE
    target.suspension_reason = None
    audit.record(
        db, "user.reactivated", actor_id=actor.id, resource_type="user", resource_id=target.id
    )
    db.commit()
    return target


def grant_role(db: Session, actor: Principal, target: User, role: Role) -> User:
    _ensure_can_manage(actor, target)
    if not can_grant(actor.roles, role):
        raise PermissionDeniedError("You cannot grant this role", code="ROLE_HIERARCHY")
    if role in target.roles:
        return target
    target.role_links.append(UserRole(role_code=role.value, granted_by_id=actor.id))
    try:
        db.flush()
    except IntegrityError as exc:  # concurrent grant
        db.rollback()
        raise ConflictError("Role already granted") from exc
    audit.record(
        db,
        "user.role_granted",
        actor_id=actor.id,
        resource_type="user",
        resource_id=target.id,
        data={"role": role.value},
    )
    db.commit()
    db.refresh(target)
    return target


def revoke_role(db: Session, actor: Principal, target: User, role: Role) -> User:
    _ensure_can_manage(actor, target)
    if not can_grant(actor.roles, role):
        raise PermissionDeniedError("You cannot revoke this role", code="ROLE_HIERARCHY")
    if role == Role.CUSTOMER:
        raise AppError("Every account keeps the CUSTOMER role", code="ROLE_REQUIRED")
    link = next((link for link in target.role_links if link.role_code == role.value), None)
    if link is None:
        return target
    target.role_links.remove(link)
    audit.record(
        db,
        "user.role_revoked",
        actor_id=actor.id,
        resource_type="user",
        resource_id=target.id,
        data={"role": role.value},
    )
    db.commit()
    db.refresh(target)
    return target
