"""FastAPI dependencies for authentication and permission checks."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth.cookies import ACCESS_COOKIE, enforce_csrf
from app.auth.models import AuthSession
from app.auth.service import resolve_access_token
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.logging import user_id_var
from app.db.session import get_db
from app.rbac.catalog import Permission, Role, permissions_for
from app.users.models import User


@dataclass(frozen=True)
class Principal:
    """The authenticated caller for this request."""

    user: User
    session: AuthSession
    roles: frozenset[Role]
    permissions: frozenset[Permission]
    via_cookie: bool

    @property
    def id(self) -> uuid.UUID:
        return self.user.id

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions

    def has_role(self, role: Role) -> bool:
        return role in self.roles


def _extract_token(request: Request) -> tuple[str | None, bool]:
    header = request.headers.get("Authorization", "")
    scheme, _, credentials = header.partition(" ")
    if scheme.lower() == "bearer" and credentials:
        return credentials.strip(), False
    cookie = request.cookies.get(ACCESS_COOKIE)
    return (cookie, True) if cookie else (None, False)


def _resolve(request: Request, db: Session) -> Principal | None:
    token, via_cookie = _extract_token(request)
    if token is None:
        return None
    if via_cookie:
        enforce_csrf(request)
    user, session = resolve_access_token(db, token)
    roles = user.roles
    request.state.user_id = str(user.id)
    user_id_var.set(str(user.id))
    return Principal(
        user=user,
        session=session,
        roles=roles,
        permissions=permissions_for(roles),
        via_cookie=via_cookie,
    )


def get_optional_principal(request: Request, db: Session = Depends(get_db)) -> Principal | None:
    """For public endpoints that personalise when signed in.

    A stale or invalid token degrades to anonymous instead of failing the page;
    CSRF violations on unsafe requests still fail.
    """
    try:
        return _resolve(request, db)
    except AuthenticationError:
        return None


def get_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    principal = _resolve(request, db)
    if principal is None:
        raise AuthenticationError("Authentication required", code="NOT_AUTHENTICATED")
    return principal


def require_permission(*required: Permission) -> Callable[..., Principal]:
    """Dependency factory: the caller must hold *all* listed permissions."""

    def dependency(principal: Principal = Depends(get_principal)) -> Principal:
        missing = [p for p in required if not principal.has(p)]
        if missing:
            raise PermissionDeniedError(
                "You do not have permission to perform this action",
                details={"missing": [p.value for p in missing]},
            )
        return principal

    return dependency


def require_any_permission(*options: Permission) -> Callable[..., Principal]:
    def dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if not any(principal.has(p) for p in options):
            raise PermissionDeniedError("You do not have permission to perform this action")
        return principal

    return dependency


def require_verified_email(principal: Principal = Depends(get_principal)) -> Principal:
    if not principal.user.email_verified:
        raise PermissionDeniedError(
            "Please verify your email address first", code="EMAIL_NOT_VERIFIED"
        )
    return principal
