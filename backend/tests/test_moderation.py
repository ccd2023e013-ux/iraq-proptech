"""Reports, moderation reasons, queues, admin overview, error log and settings."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import events
from app.audit.models import AuditLog
from app.db.session import get_sessionmaker
from app.main import create_app
from app.moderation.models import ErrorEvent, Report
from app.properties.models import Property
from app.rbac.catalog import Role
from app.users.models import User
from tests.factories import auth_headers, make_listing, make_user, upload_image
from tests.test_crm import make_agency

pytestmark = pytest.mark.db


@pytest.fixture
def owner(db_session: Session):
    return make_user(db_session, roles=[Role.PROPERTY_OWNER])


def _report(api, headers, target_type, target_id, reason="FAKE", **extra):
    return api.post(
        "/api/v1/reports",
        headers=headers,
        json={"target_type": target_type, "target_id": str(target_id), "reason": reason, **extra},
    )


def test_listing_reports_flag_and_resolve(api: TestClient, db_session: Session, owner) -> None:
    listing = make_listing(db_session, owner)
    reporters = [make_user(db_session) for _ in range(3)]
    headers = [auth_headers(api, r) for r in reporters]

    first = _report(
        api, headers[0], "PROPERTY", listing.id, "SCAM", details="يطلب عربون قبل المعاينة"
    )
    assert first.status_code == 201, first.text
    again = _report(api, headers[0], "PROPERTY", listing.id, "FAKE")
    assert again.status_code == 409 and again.json()["error"]["code"] == "ALREADY_REPORTED"
    own = _report(api, auth_headers(api, owner), "PROPERTY", listing.id)
    assert own.status_code == 422
    draft = make_listing(db_session, owner, status="DRAFT")
    assert _report(api, headers[0], "PROPERTY", draft.id).status_code == 404
    assert _report(api, headers[0], "PROPERTY", listing.id, "NONSENSE").status_code == 422

    _report(api, headers[1], "PROPERTY", listing.id, "DUPLICATE")
    db_session.expire_all()
    assert db_session.get(Property, listing.id).needs_review is False  # 2 < threshold
    _report(api, headers[2], "PROPERTY", listing.id, "INCORRECT")
    db_session.expire_all()
    assert db_session.get(Property, listing.id).needs_review is True
    assert db_session.get(Property, listing.id).status == "APPROVED"  # still live until reviewed

    moderator = auth_headers(api, make_user(db_session, roles=[Role.MODERATOR]))
    queue = api.get("/api/v1/admin/moderation/queue", headers=moderator).json()
    item = next(i for i in queue["items"] if i["property_id"] == str(listing.id))
    assert item["open_reports"] == 3 and item["needs_review"] is True

    reports = api.get("/api/v1/admin/reports", headers=moderator).json()
    assert reports["total"] == 3
    assert reports["items"][0]["open_reports_on_target"] == 3
    assert listing.reference_code in reports["items"][0]["target_label"]

    received: list[str] = []
    handler = lambda db, name, payload: received.append(name)  # noqa: E731
    events.subscribe("*", handler)
    try:
        resolved = api.post(
            f"/api/v1/admin/reports/{first.json()['id']}/resolve",
            headers=moderator,
            json={"outcome": "RESOLVED", "note": "إعلان احتيالي مؤكد", "action": "SUSPEND_LISTING"},
        )
    finally:
        events.unsubscribe("*", handler)
    assert resolved.status_code == 200, resolved.text
    assert {"property.suspended", "report.resolved"} <= set(received)
    db_session.expire_all()
    prop = db_session.get(Property, listing.id)
    assert prop.status == "SUSPENDED" and prop.status_reason_code == "REPORTED"
    statuses = db_session.execute(
        select(Report.status).where(Report.target_id == listing.id)
    ).scalars()
    assert set(statuses) == {"RESOLVED"}
    mine = api.get("/api/v1/me/reports", headers=headers[1]).json()
    assert mine[0]["status"] == "RESOLVED"
    closed = api.post(
        f"/api/v1/admin/reports/{first.json()['id']}/resolve",
        headers=moderator,
        json={"outcome": "DISMISSED", "note": "again"},
    )
    assert closed.status_code == 409
    assert db_session.execute(
        select(AuditLog).where(AuditLog.action == "report.resolved")
    ).scalar_one()


def test_dismissing_clears_the_flag(api: TestClient, db_session: Session, owner) -> None:
    listing = make_listing(db_session, owner)
    for _ in range(3):
        _report(api, auth_headers(api, make_user(db_session)), "PROPERTY", listing.id)
    moderator = auth_headers(api, make_user(db_session, roles=[Role.MODERATOR]))
    report_id = api.get("/api/v1/admin/reports", headers=moderator).json()["items"][0]["id"]
    assert (
        api.post(f"/api/v1/admin/reports/{report_id}/assign", headers=moderator).json()["status"]
        == "IN_REVIEW"
    )
    api.post(
        f"/api/v1/admin/reports/{report_id}/resolve",
        headers=moderator,
        json={"outcome": "DISMISSED", "note": "المعلومات صحيحة"},
    )
    db_session.expire_all()
    prop = db_session.get(Property, listing.id)
    assert prop.needs_review is False and prop.status == "APPROVED"


def test_user_reports_and_suspension_rights(api: TestClient, db_session: Session) -> None:
    reporter = make_user(db_session)
    target = make_user(db_session, roles=[Role.AGENT])
    h = auth_headers(api, reporter)
    assert _report(api, h, "USER", reporter.id).status_code == 422
    assert _report(api, h, "USER", uuid.uuid4()).status_code == 404
    report = _report(api, h, "USER", target.id, "SPAM").json()
    moderator = auth_headers(api, make_user(db_session, roles=[Role.MODERATOR]))
    denied = api.post(
        f"/api/v1/admin/reports/{report['id']}/resolve",
        headers=moderator,
        json={"outcome": "RESOLVED", "note": "spam", "action": "SUSPEND_USER"},
    )
    assert denied.status_code == 403  # moderators cannot suspend accounts
    wrong = api.post(
        f"/api/v1/admin/reports/{report['id']}/resolve",
        headers=moderator,
        json={"outcome": "RESOLVED", "note": "x" * 5, "action": "SUSPEND_LISTING"},
    )
    assert wrong.status_code == 422
    admin = auth_headers(api, make_user(db_session, roles=[Role.ADMIN]))
    ok = api.post(
        f"/api/v1/admin/reports/{report['id']}/resolve",
        headers=admin,
        json={"outcome": "RESOLVED", "note": "رسائل مزعجة متكررة", "action": "SUSPEND_USER"},
    )
    assert ok.status_code == 200
    db_session.expire_all()
    assert db_session.get(User, target.id).status == "SUSPENDED"
    assert api.get("/api/v1/admin/reports", headers=h).status_code == 403


def test_rejection_reason_codes_reach_the_lister(
    api: TestClient, db_session: Session, owner
) -> None:
    pending = make_listing(db_session, owner, status="PENDING_REVIEW")
    moderator = auth_headers(api, make_user(db_session, roles=[Role.MODERATOR]))
    response = api.post(
        f"/api/v1/properties/{pending.id}/moderate",
        headers=moderator,
        json={"decision": "REJECT", "reason": "الصور غير واضحة", "reason_code": "POOR_PHOTOS"},
    )
    assert response.status_code == 200, response.text
    mine = api.get(f"/api/v1/properties/{pending.id}", headers=auth_headers(api, owner)).json()
    assert mine["status"] == "REJECTED" and mine["status_reason_code"] == "POOR_PHOTOS"
    bad = api.post(
        f"/api/v1/properties/{pending.id}/moderate",
        headers=moderator,
        json={"decision": "REJECT", "reason": "x", "reason_code": "BANANAS"},
    )
    assert bad.status_code == 422


def test_queues_and_permissions(api: TestClient, db_session: Session, owner) -> None:
    old = make_listing(db_session, owner, status="PENDING_REVIEW")
    make_listing(db_session, owner)  # live, unflagged: not in the moderation queue
    unverified = make_listing(db_session, owner)
    make_listing(db_session, owner, is_demo=True)
    moderator = auth_headers(api, make_user(db_session, roles=[Role.MODERATOR]))
    queue = api.get("/api/v1/admin/moderation/queue", headers=moderator).json()
    assert [i["property_id"] for i in queue["items"]] == [str(old.id)]
    assert 0 <= queue["items"][0]["quality_score"] <= 100
    verification = api.get("/api/v1/admin/verification/queue", headers=moderator).json()
    ids = {i["property_id"] for i in verification["listings"]}
    assert str(unverified.id) in ids and len(ids) == 2  # demo listings never need verification
    customer = auth_headers(api, make_user(db_session))
    assert api.get("/api/v1/admin/moderation/queue", headers=customer).status_code == 403
    assert api.get("/api/v1/admin/verification/queue", headers=customer).status_code == 403


def test_admin_stats_and_system(api: TestClient, db_session: Session, owner) -> None:
    make_listing(db_session, owner, status="PENDING_REVIEW")
    admin = auth_headers(api, make_user(db_session, roles=[Role.ADMIN]))
    stats = api.get("/api/v1/admin/stats", headers=admin).json()
    assert stats["pending_review"] >= 1 and stats["users_total"] >= 2
    assert "ACTIVE" in stats["users_by_status"]
    system = api.get("/api/v1/admin/system", headers=admin).json()
    assert system["database"] == "ok" and system["migration"]
    assert set(system["request_network"]) == {
        "peer",
        "x_forwarded_for",
        "trusted_proxy_hops",
        "resolved_client_ip",
    }
    moderator = auth_headers(api, make_user(db_session, roles=[Role.MODERATOR]))
    assert api.get("/api/v1/admin/stats", headers=moderator).status_code == 403


def test_unhandled_errors_are_logged_without_details(db_session: Session) -> None:
    app = create_app()

    @app.get("/api/v1/__boom")
    def boom() -> None:
        raise RuntimeError("secret detail that must not leak")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/__boom", headers={"X-Request-ID": "boom-123"})
    assert response.status_code == 500
    assert "secret" not in response.text
    try:
        with get_sessionmaker()() as other:
            row = other.execute(
                select(ErrorEvent).where(ErrorEvent.request_id == "boom-123")
            ).scalar_one()
            assert row.error_type == "RuntimeError" and row.path == "/api/v1/__boom"
    finally:
        with get_sessionmaker()() as other:
            other.execute(delete(ErrorEvent).where(ErrorEvent.request_id == "boom-123"))
            other.commit()


def test_runtime_settings(api: TestClient, db_session: Session, owner) -> None:
    superadmin = auth_headers(api, make_user(db_session, roles=[Role.SUPER_ADMIN]))
    admin = auth_headers(api, make_user(db_session, roles=[Role.ADMIN]))
    listed = api.get("/api/v1/admin/settings", headers=superadmin).json()
    assert {s["key"] for s in listed} >= {"listings.lifetime_days", "site.announcement_ar"}
    assert api.get("/api/v1/admin/settings", headers=admin).status_code == 403
    url = "/api/v1/admin/settings/listings.lifetime_days"
    assert api.put(url, headers=superadmin, json={"value": 3}).status_code == 422
    assert api.put(url, headers=superadmin, json={"value": "30"}).status_code == 422
    assert api.put(url, headers=superadmin, json={"value": 30}).status_code == 200
    assert (
        api.put("/api/v1/admin/settings/nope", headers=superadmin, json={"value": 1}).status_code
        == 404
    )
    api.put(
        "/api/v1/admin/settings/site.announcement_ar",
        headers=superadmin,
        json={"value": "صيانة الليلة"},
    )
    public = api.get("/api/v1/settings/public").json()
    assert public["site.announcement_ar"] == "صيانة الليلة"
    assert "listings.lifetime_days" not in public

    pending = make_listing(db_session, owner, status="PENDING_REVIEW")
    moderator = auth_headers(api, make_user(db_session, roles=[Role.MODERATOR]))
    approved = api.post(
        f"/api/v1/properties/{pending.id}/moderate", headers=moderator, json={"decision": "APPROVE"}
    ).json()
    expires = datetime.fromisoformat(approved["expires_at"])
    assert abs(expires - (datetime.now(UTC) + timedelta(days=30))) < timedelta(hours=1)


def test_auto_approval_for_verified_agencies(api: TestClient, db_session: Session) -> None:
    owner = make_user(db_session, roles=[Role.AGENCY_OWNER])
    agency = make_agency(db_session, owner)
    superadmin = auth_headers(api, make_user(db_session, roles=[Role.SUPER_ADMIN]))
    headers = auth_headers(api, owner)

    def submit() -> str:
        draft = make_listing(
            db_session,
            owner,
            status="DRAFT",
            agency_id=agency.id,
            description_ar="وصف كافٍ لهذا العقار التجريبي الجميل",
        )
        upload_image(api, headers, str(draft.id))
        response = api.post(f"/api/v1/properties/{draft.id}/submit", headers=headers)
        assert response.status_code == 200, response.text
        return response.json()["status"]

    assert submit() == "PENDING_REVIEW"
    api.put(
        "/api/v1/admin/settings/listings.auto_approve_verified_agencies",
        headers=superadmin,
        json={"value": True},
    )
    assert submit() == "APPROVED"
    agency.status = "PENDING_VERIFICATION"
    db_session.commit()
    assert submit() == "PENDING_REVIEW"
