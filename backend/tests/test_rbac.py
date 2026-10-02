"""Authorization: role catalog, permission checks, hierarchy, privilege escalation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.rbac.catalog import (
    ROLE_NAMES,
    ROLE_PERMISSIONS,
    ROLE_RANK,
    Permission,
    Role,
    can_grant,
    can_manage,
    permissions_for,
)
from app.rbac.models import RoleRecord
from tests.factories import auth_headers, make_user

# --------------------------------------------------------------------------- pure catalog rules


def test_super_admin_has_every_permission() -> None:
    assert ROLE_PERMISSIONS[Role.SUPER_ADMIN] == frozenset(Permission)


def test_only_super_admin_manages_settings() -> None:
    holders = {r for r, perms in ROLE_PERMISSIONS.items() if Permission.SETTINGS_MANAGE in perms}
    assert holders == {Role.SUPER_ADMIN}


def test_customer_permissions_are_minimal() -> None:
    perms = ROLE_PERMISSIONS[Role.CUSTOMER]
    assert Permission.PROPERTIES_CREATE not in perms
    assert Permission.USERS_READ not in perms
    assert Permission.INQUIRIES_CREATE in perms


def test_moderator_cannot_escalate() -> None:
    perms = ROLE_PERMISSIONS[Role.MODERATOR]
    assert Permission.ROLES_ASSIGN not in perms
    assert Permission.USERS_SUSPEND not in perms
    assert Permission.PROPERTIES_MODERATE in perms


def test_hierarchy_rules() -> None:
    admin = frozenset({Role.ADMIN, Role.CUSTOMER})
    superadmin = frozenset({Role.SUPER_ADMIN})
    assert can_manage(admin, frozenset({Role.MODERATOR}))
    assert not can_manage(admin, frozenset({Role.ADMIN}))
    assert not can_manage(admin, superadmin)
    assert can_grant(admin, Role.MODERATOR)
    assert not can_grant(admin, Role.ADMIN)
    assert not can_grant(superadmin, Role.SUPER_ADMIN)  # CLI only
    assert can_grant(superadmin, Role.ADMIN)


def test_permissions_union() -> None:
    combined = permissions_for(frozenset({Role.CUSTOMER, Role.AGENT}))
    assert Permission.PROPERTIES_CREATE in combined
    assert Permission.FAVORITES_MANAGE in combined


# --------------------------------------------------------------------------- database / API


@pytest.mark.db
def test_roles_table_matches_catalog(db_session: Session) -> None:
    rows = {r.code: r for r in db_session.execute(select(RoleRecord)).scalars()}
    assert set(rows) == {r.value for r in Role}
    for role in Role:
        assert rows[role.value].rank == ROLE_RANK[role]
        assert (rows[role.value].name_ar, rows[role.value].name_en) == ROLE_NAMES[role]


@pytest.mark.db
def test_customer_cannot_access_admin_endpoints(api: TestClient, db_session: Session) -> None:
    customer = make_user(db_session)
    headers = auth_headers(api, customer)
    for method, path in [
        ("get", "/api/v1/admin/users"),
        ("get", "/api/v1/admin/audit-logs"),
        ("post", f"/api/v1/admin/users/{customer.id}/suspend"),
        ("put", f"/api/v1/admin/users/{customer.id}/roles/ADMIN"),
    ]:
        kwargs = {"json": {"reason": "test reason"}} if method == "post" else {}
        response = getattr(api, method)(path, headers=headers, **kwargs)
        assert response.status_code == 403, (path, response.text)
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.db
def test_customer_cannot_grant_self_admin(api: TestClient, db_session: Session) -> None:
    customer = make_user(db_session)
    response = api.put(
        f"/api/v1/admin/users/{customer.id}/roles/SUPER_ADMIN", headers=auth_headers(api, customer)
    )
    assert response.status_code == 403
    db_session.refresh(customer)
    assert customer.roles == frozenset({Role.CUSTOMER})


@pytest.mark.db
def test_moderator_reads_users_but_cannot_suspend(api: TestClient, db_session: Session) -> None:
    moderator = make_user(db_session, roles=[Role.MODERATOR])
    target = make_user(db_session)
    headers = auth_headers(api, moderator)
    listing = api.get("/api/v1/admin/users", params={"q": target.email[:12]}, headers=headers)
    assert listing.status_code == 200
    assert any(u["id"] == str(target.id) for u in listing.json()["items"])
    suspend = api.post(
        f"/api/v1/admin/users/{target.id}/suspend", json={"reason": "spam"}, headers=headers
    )
    assert suspend.status_code == 403


@pytest.mark.db
def test_admin_suspends_and_reactivates_customer(api: TestClient, db_session: Session) -> None:
    admin = make_user(db_session, roles=[Role.ADMIN])
    target = make_user(db_session)
    target_headers = auth_headers(api, target)
    headers = auth_headers(api, admin)

    response = api.post(
        f"/api/v1/admin/users/{target.id}/suspend",
        json={"reason": "Fake listings reported"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "SUSPENDED"
    # Existing sessions of the suspended user die immediately.
    assert api.get("/api/v1/auth/me", headers=target_headers).status_code in (401, 403)

    audit = db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "user.suspended", AuditLog.resource_id == str(target.id)
        )
    ).scalar_one()
    assert audit.actor_user_id == admin.id
    assert audit.data["reason"] == "Fake listings reported"

    back = api.post(f"/api/v1/admin/users/{target.id}/reactivate", headers=headers)
    assert back.json()["status"] == "ACTIVE"


@pytest.mark.db
@pytest.mark.parametrize("victim_role", [Role.ADMIN, Role.SUPER_ADMIN])
def test_admin_cannot_act_on_peers_or_superiors(
    api: TestClient, db_session: Session, victim_role: Role
) -> None:
    admin = make_user(db_session, roles=[Role.ADMIN])
    victim = make_user(db_session, roles=[victim_role])
    response = api.post(
        f"/api/v1/admin/users/{victim.id}/suspend",
        json={"reason": "hostile takeover"},
        headers=auth_headers(api, admin),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ROLE_HIERARCHY"


@pytest.mark.db
def test_admin_cannot_suspend_self(api: TestClient, db_session: Session) -> None:
    admin = make_user(db_session, roles=[Role.ADMIN])
    response = api.post(
        f"/api/v1/admin/users/{admin.id}/suspend",
        json={"reason": "oops"},
        headers=auth_headers(api, admin),
    )
    assert response.status_code == 403


@pytest.mark.db
def test_role_granting_respects_hierarchy(api: TestClient, db_session: Session) -> None:
    admin = make_user(db_session, roles=[Role.ADMIN])
    target = make_user(db_session)
    headers = auth_headers(api, admin)

    ok = api.put(f"/api/v1/admin/users/{target.id}/roles/MODERATOR", headers=headers)
    assert ok.status_code == 200
    assert "MODERATOR" in ok.json()["roles"]

    for role in ("ADMIN", "SUPER_ADMIN"):
        denied = api.put(f"/api/v1/admin/users/{target.id}/roles/{role}", headers=headers)
        assert denied.status_code == 403, role

    revoked = api.delete(f"/api/v1/admin/users/{target.id}/roles/MODERATOR", headers=headers)
    assert "MODERATOR" not in revoked.json()["roles"]
    customer = api.delete(f"/api/v1/admin/users/{target.id}/roles/CUSTOMER", headers=headers)
    assert customer.json()["error"]["code"] == "ROLE_REQUIRED"

    actions = set(
        db_session.execute(
            select(AuditLog.action).where(AuditLog.resource_id == str(target.id))
        ).scalars()
    )
    assert {"user.role_granted", "user.role_revoked"} <= actions


@pytest.mark.db
def test_new_role_takes_effect_on_next_request(api: TestClient, db_session: Session) -> None:
    admin = make_user(db_session, roles=[Role.ADMIN])
    target = make_user(db_session)
    target_headers = auth_headers(api, target)
    assert api.get("/api/v1/admin/users", headers=target_headers).status_code == 403
    api.put(f"/api/v1/admin/users/{target.id}/roles/MODERATOR", headers=auth_headers(api, admin))
    # Permissions are resolved per request from the DB, not baked into the JWT.
    assert api.get("/api/v1/admin/users", headers=target_headers).status_code == 200


@pytest.mark.db
def test_audit_log_access(api: TestClient, db_session: Session) -> None:
    moderator = make_user(db_session, roles=[Role.MODERATOR])
    response = api.get(
        "/api/v1/admin/audit-logs",
        params={"action": "auth.login"},
        headers=auth_headers(api, moderator),
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


@pytest.mark.db
def test_rbac_catalog_endpoint(api: TestClient, db_session: Session) -> None:
    user = make_user(db_session)
    roles = api.get("/api/v1/rbac/roles", headers=auth_headers(api, user)).json()
    assert roles[0]["code"] == "SUPER_ADMIN"
    assert {r["code"] for r in roles} == {r.value for r in Role}
