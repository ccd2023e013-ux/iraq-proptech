"""Notifications, preferences, outbox delivery, webhooks and scheduled jobs."""

from __future__ import annotations

import socket
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.notifications import jobs, service, webhooks
from app.notifications.channels import ChannelError, HttpSMSProvider
from app.notifications.models import (
    Category,
    Channel,
    JobRun,
    Notification,
    NotificationDelivery,
    WebhookDelivery,
)
from app.properties.models import Property
from app.rbac.catalog import Role
from app.search.saved import AlertFrequency
from tests.factories import auth_headers, make_listing, make_user

pytestmark = pytest.mark.db

INQUIRY = {"name": "زبون", "phone": "07701234567", "message": "هل العقار متاح للمعاينة؟"}


def _notifications(db: Session, user) -> list[Notification]:
    db.expire_all()
    return list(
        db.execute(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at)
        ).scalars()
    )


@pytest.fixture
def owner(db_session: Session):
    return make_user(db_session, roles=[Role.PROPERTY_OWNER])


@pytest.fixture
def public_dns(monkeypatch: pytest.MonkeyPatch):
    """Resolve every webhook host to a public address (no real DNS in tests)."""

    def fake(host, port, *args, **kwargs):
        address = "10.0.0.5" if host.startswith("internal") else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    monkeypatch.setattr(webhooks.socket, "getaddrinfo", fake)


def test_inquiry_notifies_the_lister_and_email_is_delivered(
    api: TestClient, db_session: Session, owner, mock_outbox
) -> None:
    listing = make_listing(db_session, owner)
    customer = make_user(db_session)
    api.post(
        f"/api/v1/properties/{listing.id}/inquiries",
        headers=auth_headers(api, customer),
        json=INQUIRY,
    )
    [note] = _notifications(db_session, owner)
    assert note.kind == "inquiry.received" and note.link.startswith("/dashboard/crm/leads/")
    assert _notifications(db_session, customer) == []

    deliveries = (
        db_session.execute(
            select(NotificationDelivery).where(NotificationDelivery.notification_id == note.id)
        )
        .scalars()
        .all()
    )
    assert [d.channel for d in deliveries] == ["EMAIL"] and deliveries[0].status == "PENDING"
    stats = service.process_deliveries(db_session)
    assert stats["sent"] == 1
    db_session.expire_all()
    assert db_session.get(NotificationDelivery, deliveries[0].id).status == "SENT"
    assert any(m.to == owner.email and "notification" in m.tags for m in mock_outbox.outbox())

    headers = auth_headers(api, owner)
    assert api.get("/api/v1/me/notifications/unread-count", headers=headers).json() == {"unread": 1}
    listed = api.get("/api/v1/me/notifications", headers=headers).json()
    assert listed["items"][0]["title_ar"] == "استفسار جديد عن إعلانك"
    assert api.post(f"/api/v1/me/notifications/{note.id}/read", headers=headers).status_code == 204
    assert api.get("/api/v1/me/notifications/unread-count", headers=headers).json() == {"unread": 0}
    stranger = auth_headers(api, customer)
    assert api.post(f"/api/v1/me/notifications/{note.id}/read", headers=stranger).status_code == 404


def test_preferences_control_external_channels(api: TestClient, db_session: Session, owner) -> None:
    headers = auth_headers(api, owner)
    assert (
        api.get("/api/v1/me/notification-preferences", headers=headers).json()["email_enabled"]
        is True
    )
    assert (
        api.put(
            "/api/v1/me/notification-preferences",
            headers=headers,
            json={"email_enabled": True, "categories": {"bogus": False}},
        ).status_code
        == 422
    )
    sms = api.put(
        "/api/v1/me/notification-preferences", headers=headers, json={"sms_enabled": True}
    )
    assert sms.status_code == 422 and sms.json()["error"]["code"] == "PHONE_REQUIRED"
    api.put(
        "/api/v1/me/notification-preferences",
        headers=headers,
        json={"email_enabled": True, "categories": {"leads": False}},
    )
    note = service.notify(db_session, owner.id, kind="x", category=Category.LEADS, title=("a", "a"))
    assert note is not None  # in-app always
    assert (
        db_session.execute(
            select(NotificationDelivery).where(NotificationDelivery.notification_id == note.id)
        ).first()
        is None
    )
    other = service.notify(
        db_session, owner.id, kind="y", category=Category.LISTINGS, title=("b", "b")
    )
    assert (
        db_session.execute(
            select(NotificationDelivery).where(NotificationDelivery.notification_id == other.id)
        )
        .scalar_one()
        .channel
        == "EMAIL"
    )


def test_sms_delivery_through_mock_and_http_gateway(db_session: Session) -> None:
    user = make_user(db_session)
    user.phone = "+9647701234567"
    db_session.commit()
    pref = service.preferences(db_session, user.id)
    pref.sms_enabled, pref.email_enabled = True, False
    note = service.notify(
        db_session,
        user.id,
        kind="t",
        category=Category.ACCOUNT,
        title=("رسالة", "msg"),
        channels=(Channel.SMS,),
    )
    db_session.commit()
    assert service.process_deliveries(db_session)["sent"] == 1
    delivery = db_session.execute(
        select(NotificationDelivery).where(NotificationDelivery.notification_id == note.id)
    ).scalar_one()
    assert delivery.provider == "mock" and delivery.status == "SENT"

    seen: dict[str, Any] = {}

    def ok(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200)

    HttpSMSProvider(
        "https://sms.example.com/send", "tok", httpx.Client(transport=httpx.MockTransport(ok))
    ).send("+9647701234567", "مرحبا")
    assert seen["auth"] == "Bearer tok"
    failing = HttpSMSProvider(
        "https://sms.example.com/send",
        "tok",
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))),
    )
    with pytest.raises(ChannelError):
        failing.send("+9647701234567", "x")


def test_failed_deliveries_retry_with_backoff_then_give_up(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = make_user(db_session)
    note = service.notify(
        db_session, user.id, kind="t", category=Category.ACCOUNT, title=("a", "a")
    )
    db_session.commit()

    class Broken:
        name = "broken"

        def send(self, message):
            raise RuntimeError("smtp down")

    monkeypatch.setattr(service, "get_email_provider", lambda: Broken())
    delivery = db_session.execute(
        select(NotificationDelivery).where(NotificationDelivery.notification_id == note.id)
    ).scalar_one()
    for attempt in range(1, service.MAX_ATTEMPTS + 1):
        delivery.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        db_session.commit()
        service.process_deliveries(db_session)
        db_session.refresh(delivery)
        assert delivery.attempts == attempt
    assert delivery.status == "FAILED" and "smtp down" in delivery.last_error


def test_messages_and_moderation_notify_the_right_people(
    api: TestClient, db_session: Session, owner
) -> None:
    listing = make_listing(db_session, owner)
    customer = make_user(db_session)
    customer_h = auth_headers(api, customer)
    api.post(f"/api/v1/properties/{listing.id}/inquiries", headers=customer_h, json=INQUIRY)
    conv = api.get("/api/v1/me/conversations", headers=customer_h).json()[0]["id"]
    api.post(
        f"/api/v1/conversations/{conv}/messages",
        headers=auth_headers(api, owner),
        json={"body": "أهلاً، العقار متاح"},
    )
    kinds = [n.kind for n in _notifications(db_session, customer)]
    assert kinds == ["message.received"]

    pending = make_listing(db_session, owner, status="PENDING_REVIEW")
    moderator = auth_headers(api, make_user(db_session, roles=[Role.MODERATOR]))
    api.post(
        f"/api/v1/properties/{pending.id}/moderate",
        headers=moderator,
        json={"decision": "REJECT", "reason": "صور غير واضحة", "reason_code": "POOR_PHOTOS"},
    )
    rejected = [n for n in _notifications(db_session, owner) if n.kind == "listing.rejected"]
    assert rejected and rejected[0].link == f"/dashboard/properties/{pending.id}"


def test_dedupe_keys(db_session: Session) -> None:
    user = make_user(db_session)
    first = service.notify(
        db_session,
        user.id,
        kind="k",
        category=Category.REMINDERS,
        title=("a", "a"),
        dedupe_key="same",
    )
    second = service.notify(
        db_session,
        user.id,
        kind="k",
        category=Category.REMINDERS,
        title=("a", "a"),
        dedupe_key="same",
    )
    assert first is not None and second is None


# --- webhooks


def test_webhook_lifecycle_and_signing(
    api: TestClient, db_session: Session, owner, public_dns, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = auth_headers(api, make_user(db_session, roles=[Role.ADMIN]))
    created = api.post(
        "/api/v1/admin/webhooks",
        headers=admin,
        json={
            "name": "n8n",
            "url": "https://hooks.example.com/proptech",
            "events": ["listing.created", "lead.created"],
        },
    )
    assert created.status_code == 201, created.text
    hook = created.json()
    assert hook["secret"].startswith("whsec_")
    assert "secret" not in api.get("/api/v1/admin/webhooks", headers=admin).json()[0]

    for bad_url, reason in (
        ("http://hooks.example.com/x", "https"),
        ("https://internal.example.com/x", "private"),
        ("https://user:pass@hooks.example.com/x", "credentials"),
        ("ftp://hooks.example.com/x", "http"),
    ):
        response = api.post(
            "/api/v1/admin/webhooks",
            headers=admin,
            json={"name": "bad", "url": bad_url, "events": ["*"]},
        )
        assert response.status_code == 422 and reason in response.text, bad_url
    assert (
        api.post(
            "/api/v1/admin/webhooks",
            headers=admin,
            json={"name": "x", "url": "https://hooks.example.com/y", "events": ["nope"]},
        ).status_code
        == 422
    )

    # creating a listing through the API queues a signed delivery
    from tests.factories import basra, listing_payload

    gov, city = basra(db_session)
    api.post(
        "/api/v1/properties", headers=auth_headers(api, owner), json=listing_payload(gov, city)
    )
    queued = db_session.execute(select(WebhookDelivery)).scalars().all()
    assert [d.event for d in queued] == ["listing.created"]

    calls: list[dict[str, Any]] = []

    def receiver(url, secret, event, delivery_id, payload):
        body = webhooks.json.dumps(payload).encode()
        calls.append(
            {"url": url, "event": event, "signature": webhooks.sign(secret, body), "body": body}
        )
        return 200

    assert service.process_webhooks(db_session, poster=receiver)["sent"] == 1
    assert calls[0]["event"] == "listing.created"
    assert webhooks.verify(hook["secret"], calls[0]["body"], calls[0]["signature"])
    assert not webhooks.verify("wrong", calls[0]["body"], calls[0]["signature"])
    stale = webhooks.sign(hook["secret"], b"{}", timestamp=1)
    assert not webhooks.verify(hook["secret"], b"{}", stale)

    test = api.post(f"/api/v1/admin/webhooks/{hook['id']}/test", headers=admin)
    assert test.status_code == 202
    deliveries = api.get(f"/api/v1/admin/webhooks/{hook['id']}/deliveries", headers=admin).json()
    assert {d["event"] for d in deliveries} == {"listing.created", "webhook.test"}
    customer = auth_headers(api, make_user(db_session))
    assert api.get("/api/v1/admin/webhooks", headers=customer).status_code == 403
    assert api.delete(f"/api/v1/admin/webhooks/{hook['id']}", headers=admin).status_code == 204


def test_failing_webhooks_back_off_and_auto_disable(
    api: TestClient, db_session: Session, owner, public_dns, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "AUTO_DISABLE_AFTER", 2)
    admin = auth_headers(api, make_user(db_session, roles=[Role.ADMIN]))
    hook = api.post(
        "/api/v1/admin/webhooks",
        headers=admin,
        json={"name": "flaky", "url": "https://hooks.example.com/x", "events": ["*"]},
    ).json()
    for _ in range(2):
        api.post(f"/api/v1/admin/webhooks/{hook['id']}/test", headers=admin)
    stats = service.process_webhooks(db_session, poster=lambda *a: 500)
    assert stats["retry"] == 2
    listed = api.get("/api/v1/admin/webhooks", headers=admin).json()[0]
    assert listed["is_active"] is False and listed["last_status"] == 500
    rows = db_session.execute(select(WebhookDelivery)).scalars().all()
    assert all(r.next_attempt_at > datetime.now(UTC) for r in rows)


def test_registration_emits_user_registered_webhook(
    api: TestClient, db_session: Session, public_dns
) -> None:
    admin = auth_headers(api, make_user(db_session, roles=[Role.ADMIN]))
    api.post(
        "/api/v1/admin/webhooks",
        headers=admin,
        json={"name": "crm", "url": "https://hooks.example.com/u", "events": ["user.registered"]},
    )
    api.post(
        "/api/v1/auth/register",
        json={
            "email": "new-user@example.com",
            "password": "Correct-Horse-9-Battery",
            "full_name": "مستخدم جديد",
        },
    )
    events = [d.event for d in db_session.execute(select(WebhookDelivery)).scalars()]
    assert events == ["user.registered"]


# --- scheduled jobs


def test_saved_search_alerts(api: TestClient, db_session: Session, owner) -> None:
    customer = make_user(db_session)
    headers = auth_headers(api, customer)
    api.post(
        "/api/v1/me/saved-searches",
        headers=headers,
        json={"name": "بيوت", "filters": {"purpose": "SALE"}, "alert_frequency": "INSTANT"},
    )
    assert jobs.saved_search_alerts(db_session, AlertFrequency.INSTANT)["alerted"] == 0
    make_listing(db_session, owner, price_amount=Decimal("100000000"))
    assert jobs.saved_search_alerts(db_session, AlertFrequency.INSTANT)["alerted"] == 1
    [note] = _notifications(db_session, customer)
    assert note.kind == "saved_search.matches" and "1" in note.title_ar
    assert jobs.saved_search_alerts(db_session, AlertFrequency.INSTANT)["alerted"] == 0
    assert jobs.saved_search_alerts(db_session, AlertFrequency.DAILY)["checked"] == 0


def test_reminders_and_expiry(api: TestClient, db_session: Session, owner) -> None:
    listing = make_listing(db_session, owner)
    customer = make_user(db_session)
    api.post(
        f"/api/v1/properties/{listing.id}/inquiries",
        headers=auth_headers(api, customer),
        json=INQUIRY,
    )
    owner_h = auth_headers(api, owner)
    lead_id = api.get("/api/v1/crm/leads", headers=owner_h).json()["items"][0]["id"]
    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    api.patch(f"/api/v1/crm/leads/{lead_id}", headers=owner_h, json={"next_follow_up_at": past})
    api.post(
        "/api/v1/crm/tasks",
        headers=owner_h,
        json={"title": "اتصال", "lead_id": lead_id, "due_at": past},
    )
    assert jobs.reminders(db_session)["reminders"] == 2
    assert jobs.reminders(db_session)["reminders"] == 0  # deduplicated

    expired = make_listing(db_session, owner)
    expired.expires_at = datetime.now(UTC) - timedelta(days=1)
    db_session.commit()
    assert jobs.expire_listings(db_session)["expired"] == 1
    db_session.expire_all()
    assert db_session.get(Property, expired.id).status == "EXPIRED"
    assert any(n.kind == "listing.expired" for n in _notifications(db_session, owner))


def test_job_runs_are_recorded(api: TestClient, db_session: Session) -> None:
    ok = service.run_job(db_session, "unit.ok", lambda db: {"n": 1})
    assert ok.status == "SUCCEEDED" and ok.detail == {"n": 1}

    def boom(db):
        raise RuntimeError("bad")

    failed = service.run_job(db_session, "unit.fail", boom)
    assert failed.status == "FAILED" and "bad" in failed.error
    admin = auth_headers(api, make_user(db_session, roles=[Role.ADMIN]))
    names = {j["name"] for j in api.get("/api/v1/admin/jobs", headers=admin).json()}
    assert {"unit.ok", "unit.fail"} <= names
    assert db_session.execute(select(JobRun)).scalars().all()
    moderator = auth_headers(api, make_user(db_session, roles=[Role.MODERATOR]))
    assert api.get("/api/v1/admin/jobs", headers=moderator).status_code == 403
    assert "counts" in api.get("/api/v1/admin/notifications/deliveries", headers=admin).json()
