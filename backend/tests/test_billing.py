"""Billing: demo checkout, idempotent fulfilment, promotions, credits, refunds, admin."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.billing import service
from app.billing.models import Plan, Promotion, Subscription
from app.core.config import Settings, get_settings
from app.rbac.catalog import Role
from tests.factories import auth_headers, make_listing, make_user

pytestmark = pytest.mark.db


def _plan(db: Session, **overrides) -> Plan:
    fields = dict(
        code="feature-7",
        kind="PROMOTION",
        name_ar="تمييز",
        name_en="Feature",
        price_amount=Decimal("10000"),
        currency="IQD",
        duration_days=7,
        featured_credits=0,
        is_active=True,
        is_demo=True,
        sort_order=0,
    )
    fields.update(overrides)
    plan = Plan(**fields)
    db.add(plan)
    db.commit()
    return plan


def _pay(api: TestClient, headers, body, outcome="SUCCEEDED") -> dict:
    created = api.post("/api/v1/billing/checkout", headers=headers, json=body)
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["payment"]["is_demo"] is True and data["payment"]["status"] == "PENDING"
    assert data["redirect_url"] == f"/billing/demo/{data['payment']['id']}"
    done = api.post(
        f"/api/v1/billing/payments/{data['payment']['id']}/demo-complete",
        headers=headers,
        json={"outcome": outcome},
    )
    assert done.status_code == 200, done.text
    return done.json()


def test_config_and_public_plans(api: TestClient, db_session: Session) -> None:
    _plan(db_session)
    _plan(db_session, code="hidden", is_active=False)
    assert api.get("/api/v1/billing/config").json() == {
        "enabled": True,
        "provider": "demo",
        "demo": True,
    }
    codes = [p["code"] for p in api.get("/api/v1/billing/plans").json()]
    assert codes == ["feature-7"]


def test_demo_payments_disabled_in_production_unless_opted_in() -> None:
    prod = Settings(app_env="production", jwt_secret="x" * 40, payment_provider="demo")
    assert prod.effective_payment_provider == "none"
    opted = Settings(
        app_env="production",
        jwt_secret="x" * 40,
        payment_provider="demo",
        payment_demo_in_production=True,
    )
    assert opted.effective_payment_provider == "demo"


def test_promotion_purchase_features_listing_once(api: TestClient, db_session: Session) -> None:
    owner = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    listing = make_listing(db_session, owner)
    _plan(db_session)
    h = auth_headers(api, owner)
    paid = _pay(api, h, {"plan_code": "feature-7", "property_id": str(listing.id)})
    assert paid["status"] == "SUCCEEDED"

    db_session.expire_all()
    assert listing.featured_until is not None
    assert listing.featured_until > datetime.now(UTC) + timedelta(days=6)
    featured = api.get("/api/v1/properties/featured").json()
    assert [c["id"] for c in featured] == [str(listing.id)]
    assert featured[0]["is_featured"] is True
    search = api.get("/api/v1/search/properties").json()
    assert next(c for c in search["items"] if c["id"] == str(listing.id))["is_featured"] is True

    # A repeated provider answer changes nothing (idempotent fulfilment).
    again = api.post(
        f"/api/v1/billing/payments/{paid['id']}/demo-complete",
        headers=h,
        json={"outcome": "SUCCEEDED"},
    )
    assert again.status_code == 200
    promos = list(db_session.execute(select(Promotion)).scalars())
    assert len(promos) == 1 and promos[0].is_demo is True

    # A second purchase extends from the current end instead of overlapping.
    first_end = listing.featured_until
    _pay(api, h, {"plan_code": "feature-7", "property_id": str(listing.id)})
    db_session.expire_all()
    assert listing.featured_until == first_end + timedelta(days=7)


def test_failed_payment_buys_nothing(api: TestClient, db_session: Session) -> None:
    owner = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    listing = make_listing(db_session, owner)
    _plan(db_session)
    failed = _pay(
        api,
        auth_headers(api, owner),
        {"plan_code": "feature-7", "property_id": str(listing.id)},
        outcome="FAILED",
    )
    assert failed["status"] == "FAILED"
    db_session.expire_all()
    assert listing.featured_until is None


def test_cannot_promote_someone_elses_or_unpublished_listing(
    api: TestClient, db_session: Session
) -> None:
    owner = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    stranger = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    listing = make_listing(db_session, owner)
    draft = make_listing(db_session, owner, status="DRAFT")
    _plan(db_session)
    r = api.post(
        "/api/v1/billing/checkout",
        headers=auth_headers(api, stranger),
        json={"plan_code": "feature-7", "property_id": str(listing.id)},
    )
    assert r.status_code == 404
    r = api.post(
        "/api/v1/billing/checkout",
        headers=auth_headers(api, owner),
        json={"plan_code": "feature-7", "property_id": str(draft.id)},
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "NOT_PUBLISHED"
    r = api.post(
        "/api/v1/billing/checkout",
        headers=auth_headers(api, owner),
        json={"plan_code": "feature-7"},
    )
    assert r.json()["error"]["code"] == "PROPERTY_REQUIRED"


def test_payments_are_private_to_the_payer(api: TestClient, db_session: Session) -> None:
    owner = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    other = make_user(db_session)
    listing = make_listing(db_session, owner)
    _plan(db_session)
    created = api.post(
        "/api/v1/billing/checkout",
        headers=auth_headers(api, owner),
        json={"plan_code": "feature-7", "property_id": str(listing.id)},
    ).json()
    pid = created["payment"]["id"]
    other_h = auth_headers(api, other)
    assert api.get(f"/api/v1/billing/payments/{pid}", headers=other_h).status_code == 404
    r = api.post(
        f"/api/v1/billing/payments/{pid}/demo-complete",
        headers=other_h,
        json={"outcome": "SUCCEEDED"},
    )
    assert r.status_code == 404


def test_subscription_credits_and_cancellation(api: TestClient, db_session: Session) -> None:
    owner = make_user(db_session, roles=[Role.AGENCY_OWNER])
    listing = make_listing(db_session, owner)
    _plan(
        db_session, code="agency-monthly", kind="SUBSCRIPTION", duration_days=30, featured_credits=1
    )
    h = auth_headers(api, owner)
    _pay(api, h, {"plan_code": "agency-monthly"})
    me = api.get("/api/v1/me/billing", headers=h).json()
    assert me["subscription"]["credits_remaining"] == 1
    assert me["subscription_plan"]["code"] == "agency-monthly"

    second = api.post("/api/v1/billing/checkout", headers=h, json={"plan_code": "agency-monthly"})
    assert second.status_code == 409

    redeemed = api.post(
        "/api/v1/billing/promotions/redeem", headers=h, json={"property_id": str(listing.id)}
    )
    assert redeemed.status_code == 201
    none_left = api.post(
        "/api/v1/billing/promotions/redeem", headers=h, json={"property_id": str(listing.id)}
    )
    assert none_left.status_code == 402 and none_left.json()["error"]["code"] == "NO_CREDITS"

    cancel = api.post("/api/v1/me/subscription/cancel", headers=h)
    assert cancel.json()["cancel_at_period_end"] is True

    sub = db_session.execute(select(Subscription)).scalar_one()
    sub.current_period_end = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()
    assert service.expire_subscriptions(db_session) == {"expired": 1}
    db_session.expire_all()
    assert sub.status == "CANCELED"


def test_admin_plans_refunds_and_summary(api: TestClient, db_session: Session) -> None:
    root = make_user(db_session, roles=[Role.SUPER_ADMIN])
    admin = make_user(db_session, roles=[Role.ADMIN])
    owner = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    listing = make_listing(db_session, owner)
    root_h = auth_headers(api, root)

    body = {
        "code": "feature-14",
        "kind": "PROMOTION",
        "name_ar": "تمييز أسبوعين",
        "name_en": "Feature 14 days",
        "price_amount": "15000",
        "currency": "IQD",
        "duration_days": 14,
    }
    assert (
        api.post(
            "/api/v1/admin/billing/plans", headers=auth_headers(api, admin), json=body
        ).status_code
        == 403
    )
    created = api.post("/api/v1/admin/billing/plans", headers=root_h, json=body)
    assert created.status_code == 201
    assert api.post("/api/v1/admin/billing/plans", headers=root_h, json=body).status_code == 409
    # Prices cannot be edited after creation.
    patch = api.patch(
        f"/api/v1/admin/billing/plans/{created.json()['id']}",
        headers=root_h,
        json={"price_amount": "1"},
    )
    assert patch.status_code == 422

    paid = _pay(
        api, auth_headers(api, owner), {"plan_code": "feature-14", "property_id": str(listing.id)}
    )
    summary = api.get("/api/v1/admin/billing/summary", headers=root_h).json()
    assert summary["revenue"] == [
        {"currency": "IQD", "is_demo": True, "payments": 1, "amount": "15000.00"}
    ]

    refunded = api.post(
        f"/api/v1/admin/billing/payments/{paid['id']}/refund",
        headers=root_h,
        json={"reason": "duplicate purchase"},
    )
    assert refunded.status_code == 200 and refunded.json()["status"] == "REFUNDED"
    db_session.expire_all()
    assert listing.featured_until is None
    again = api.post(
        f"/api/v1/admin/billing/payments/{paid['id']}/refund",
        headers=root_h,
        json={"reason": "again"},
    )
    assert again.status_code == 409
    actions = set(db_session.execute(select(AuditLog.action)).scalars())
    assert {
        "billing.plan_created",
        "billing.payment_succeeded",
        "billing.payment_refunded",
    } <= actions


def test_billing_disabled_returns_503(
    api: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "payment_provider", "none")
    owner = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    _plan(db_session)
    r = api.post(
        "/api/v1/billing/checkout",
        headers=auth_headers(api, owner),
        json={"plan_code": "agency"},
    )
    assert r.status_code == 503 and r.json()["error"]["code"] == "BILLING_DISABLED"
    assert api.get("/api/v1/billing/config").json()["enabled"] is False
