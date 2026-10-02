"""Test data builders and API helpers."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.notifications.email import MockEmailProvider
from app.rbac.catalog import Role
from app.users.models import User, UserRole, UserStatus

DEFAULT_PASSWORD = "Correct-Horse-Battery-9"


def make_user(
    db: Session,
    *,
    email: str | None = None,
    password: str = DEFAULT_PASSWORD,
    roles: Iterable[Role] = (Role.CUSTOMER,),
    verified: bool = True,
    name: str = "مستخدم تجريبي",
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    user = User(
        email=email or f"user-{uuid.uuid4().hex[:10]}@example.test",
        full_name=name,
        password_hash=hash_password(password),
        preferred_locale="ar",
        status=status,
        email_verified_at=datetime.now(UTC) if verified else None,
    )
    for role in {Role.CUSTOMER, *roles}:
        user.role_links.append(UserRole(role_code=role.value))
    db.add(user)
    # Commit (a savepoint release inside the test transaction) so that a failing
    # request, which rolls back its own work, cannot undo test fixtures.
    db.commit()
    return user


def login(api: TestClient, email: str, password: str = DEFAULT_PASSWORD) -> dict[str, str]:
    """Bearer-mode login; returns tokens."""
    response = api.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-Auth-Transport": "bearer"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return {"access": body["access_token"], "refresh": body["refresh_token"]}


def auth_headers(api: TestClient, user: User, password: str = DEFAULT_PASSWORD) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(api, user.email, password)['access']}"}


def token_from_outbox(outbox: MockEmailProvider, tag: str) -> str:
    messages = [m for m in outbox.outbox() if tag in m.tags]
    assert messages, f"no {tag} email sent"
    match = re.search(r"token=([A-Za-z0-9_-]+)", messages[-1].text)
    assert match, "no token link in email"
    return match.group(1)
