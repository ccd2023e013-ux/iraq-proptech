"""Property lifecycle, validation, privacy and authorization (real PostGIS)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.properties.models import PropertyPriceHistory
from app.rbac.catalog import Role
from tests.factories import (
    BASRA_ASHAR,
    auth_headers,
    basra,
    listing_payload,
    make_district,
    make_neighborhood,
    make_user,
    publish,
    upload_image,
)

pytestmark = pytest.mark.db


@pytest.fixture
def owner(db_session: Session):
    return make_user(db_session, roles=[Role.PROPERTY_OWNER])


@pytest.fixture
def owner_h(api: TestClient, owner) -> dict[str, str]:
    return auth_headers(api, owner)


@pytest.fixture
def mod_h(api: TestClient, db_session: Session) -> dict[str, str]:
    return auth_headers(api, make_user(db_session, roles=[Role.MODERATOR]))


@pytest.fixture
def place(db_session: Session):
    return basra(db_session)


def _create(api: TestClient, headers: dict[str, str], place, **overrides) -> dict:
    response = api.post(
        "/api/v1/properties", json=listing_payload(*place, **overrides), headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------------------- creation & validation


def test_customer_cannot_create_listing(api: TestClient, db_session: Session, place) -> None:
    headers = auth_headers(api, make_user(db_session))
    response = api.post("/api/v1/properties", json=listing_payload(*place), headers=headers)
    assert response.status_code == 403


def test_unverified_owner_cannot_create_listing(
    api: TestClient, db_session: Session, place
) -> None:
    user = make_user(db_session, roles=[Role.PROPERTY_OWNER], verified=False)
    response = api.post(
        "/api/v1/properties", json=listing_payload(*place), headers=auth_headers(api, user)
    )
    assert response.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"


def test_create_listing_as_draft(api: TestClient, owner_h, place, db_session: Session) -> None:
    body = _create(api, owner_h, place)
    assert body["status"] == "DRAFT"
    assert body["reference_code"].startswith("BSR-")
    assert body["price_amount"] == "250000000.00"
    assert body["currency"] == "IQD"
    assert body["amenities"] == ["GENERATOR_SUBSCRIPTION", "NATIONAL_GRID"]
    assert body["can_edit"] is True
    assert body["exact_location"] == {"lon": BASRA_ASHAR[0], "lat": BASRA_ASHAR[1]}
    assert body["is_demo"] is False
    history = db_session.execute(
        select(PropertyPriceHistory).where(PropertyPriceHistory.property_id == body["id"])
    ).scalars()
    assert len(list(history)) == 1
    audit = db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "property.created", AuditLog.resource_id == body["id"]
        )
    ).scalar_one()
    assert audit.data["reference"] == body["reference_code"]


def test_original_currency_is_preserved(api: TestClient, owner_h, place) -> None:
    body = _create(api, owner_h, place, price_amount="185000", currency="USD")
    assert (body["price_amount"], body["currency"]) == ("185000.00", "USD")


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"purpose": "RENT"}, "VALIDATION_ERROR"),  # rent needs a period
        ({"price_on_request": True}, "VALIDATION_ERROR"),  # price and on-request
        ({"price_amount": None}, "VALIDATION_ERROR"),  # no price at all
        ({"price_amount": "-5"}, "VALIDATION_ERROR"),
        ({"location": {"lon": 2.35, "lat": 48.85}}, "VALIDATION_ERROR"),  # Paris
        ({"amenities": ["TELEPORTER"]}, "INVALID_AMENITY"),
        ({"property_type_code": "CASTLE"}, "INVALID_PROPERTY_TYPE"),
        ({"bedrooms": 500}, "VALIDATION_ERROR"),
    ],
)
def test_listing_validation(api: TestClient, owner_h, place, overrides, code) -> None:
    response = api.post(
        "/api/v1/properties", json=listing_payload(*place, **overrides), headers=owner_h
    )
    assert response.status_code in (400, 422), response.text
    assert response.json()["error"]["code"] == code


def test_city_must_belong_to_governorate(
    api: TestClient, owner_h, place, db_session: Session
) -> None:
    from app.geo.models import Governorate

    baghdad = db_session.execute(select(Governorate).where(Governorate.code == "BGD")).scalar_one()
    response = api.post(
        "/api/v1/properties",
        json=listing_payload(baghdad, place[1]),
        headers=owner_h,
    )
    assert response.json()["error"]["code"] == "INVALID_LOCATION"


def test_rent_listing_with_period(api: TestClient, owner_h, place) -> None:
    body = _create(
        api, owner_h, place, purpose="RENT", rent_period="MONTHLY", price_amount="750000"
    )
    assert (body["purpose"], body["rent_period"]) == ("RENT", "MONTHLY")


# --------------------------------------------------------------------------- visibility & privacy


def test_drafts_are_invisible_to_others(
    api: TestClient, owner_h, place, db_session: Session
) -> None:
    listing = _create(api, owner_h, place)
    assert api.get(f"/api/v1/properties/{listing['id']}").status_code == 404
    stranger = auth_headers(api, make_user(db_session))
    assert api.get(f"/api/v1/properties/{listing['id']}", headers=stranger).status_code == 404
    patch = api.patch(
        f"/api/v1/properties/{listing['id']}", json={"title_ar": "عنوان مختطف"}, headers=stranger
    )
    assert patch.status_code == 404


def test_full_lifecycle_and_public_view(api: TestClient, owner_h, mod_h, place) -> None:
    listing = _create(api, owner_h, place, street="شارع الكورنيش")
    incomplete = api.post(f"/api/v1/properties/{listing['id']}/submit", headers=owner_h)
    assert incomplete.json()["error"]["code"] == "SUBMISSION_INCOMPLETE"
    assert "NO_IMAGES" in incomplete.json()["error"]["details"]

    approved = publish(api, owner_h, mod_h, listing["id"])
    assert approved["status"] == "APPROVED"
    assert approved["published_at"] and approved["expires_at"]

    public = api.get(f"/api/v1/properties/{listing['id']}").json()
    assert public["exact_location"] is None  # private
    assert public["street"] is None  # could identify the house
    assert public["can_edit"] is False
    assert public["display_location"] != {"lon": BASRA_ASHAR[0], "lat": BASRA_ASHAR[1]}
    assert len(public["media"]) == 1
    assert public["lister"]["kind"] == "owner"
    assert public["lister"]["phone"] is None  # not consented

    listing_page = api.get("/api/v1/properties").json()
    assert any(item["id"] == listing["id"] for item in listing_page["items"])


@pytest.mark.parametrize("privacy", ["EXACT", "HIDDEN"])
def test_location_privacy_modes(api: TestClient, owner_h, place, privacy: str) -> None:
    listing = _create(api, owner_h, place, location_privacy=privacy)
    expected = {"lon": BASRA_ASHAR[0], "lat": BASRA_ASHAR[1]} if privacy == "EXACT" else None
    assert listing["display_location"] == expected


def test_approximate_location_uses_neighborhood_centre(
    api: TestClient, owner_h, place, db_session: Session
) -> None:
    district = make_district(db_session, place[1])
    hood = make_neighborhood(db_session, district, centroid=(47.8200, 30.5120))
    listing = _create(
        api,
        owner_h,
        place,
        district_id=str(district.id),
        neighborhood_id=str(hood.id),
    )
    assert listing["display_location"] == {"lon": 47.82, "lat": 30.512}
    assert listing["neighborhood"]["name_en"] == "Al-Jumhuriya"


def test_neighborhood_must_match_district(
    api: TestClient, owner_h, place, db_session: Session
) -> None:
    d1 = make_district(db_session, place[1], slug="d1")
    d2 = make_district(db_session, place[1], slug="d2")
    hood = make_neighborhood(db_session, d2)
    response = api.post(
        "/api/v1/properties",
        json=listing_payload(*place, district_id=str(d1.id), neighborhood_id=str(hood.id)),
        headers=owner_h,
    )
    assert response.json()["error"]["code"] == "INVALID_LOCATION"


# --------------------------------------------------------------------------- updates & history


def test_price_change_is_recorded_and_flags_review(
    api: TestClient, owner_h, mod_h, place, db_session: Session
) -> None:
    listing = _create(api, owner_h, place)
    publish(api, owner_h, mod_h, listing["id"])
    response = api.patch(
        f"/api/v1/properties/{listing['id']}", json={"price_amount": "240000000"}, headers=owner_h
    )
    assert response.status_code == 200, response.text
    assert response.json()["needs_review"] is True
    history = api.get(f"/api/v1/properties/{listing['id']}/price-history").json()
    assert [h["price_amount"] for h in history] == ["250000000.00", "240000000.00"]


def test_update_rechecks_cross_field_rules(api: TestClient, owner_h, place) -> None:
    listing = _create(api, owner_h, place)
    response = api.patch(
        f"/api/v1/properties/{listing['id']}", json={"purpose": "RENT"}, headers=owner_h
    )
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_other_user_cannot_edit_public_listing(
    api: TestClient, owner_h, mod_h, place, db_session: Session
) -> None:
    listing = _create(api, owner_h, place)
    publish(api, owner_h, mod_h, listing["id"])
    other = auth_headers(api, make_user(db_session, roles=[Role.PROPERTY_OWNER]))
    response = api.patch(
        f"/api/v1/properties/{listing['id']}", json={"price_amount": "1"}, headers=other
    )
    assert response.status_code == 403
    deleted = api.delete(f"/api/v1/properties/{listing['id']}", headers=other)
    assert deleted.status_code == 403


def test_admin_can_manage_any_listing(api: TestClient, owner_h, place, db_session: Session) -> None:
    listing = _create(api, owner_h, place)
    admin = auth_headers(api, make_user(db_session, roles=[Role.ADMIN]))
    response = api.patch(
        f"/api/v1/properties/{listing['id']}",
        json={"title_ar": "عنوان معدل من الإدارة"},
        headers=admin,
    )
    assert response.status_code == 200


# --------------------------------------------------------------------------- moderation & lifecycle


def test_moderation_rules(api: TestClient, owner_h, mod_h, place, db_session: Session) -> None:
    listing = _create(api, owner_h, place)
    upload_image(api, owner_h, listing["id"])
    api.post(f"/api/v1/properties/{listing['id']}/submit", headers=owner_h)

    no_reason = api.post(
        f"/api/v1/properties/{listing['id']}/moderate", json={"decision": "REJECT"}, headers=mod_h
    )
    assert no_reason.json()["error"]["code"] == "REASON_REQUIRED"
    owner_tries = api.post(
        f"/api/v1/properties/{listing['id']}/moderate",
        json={"decision": "APPROVE"},
        headers=owner_h,
    )
    assert owner_tries.status_code == 403

    rejected = api.post(
        f"/api/v1/properties/{listing['id']}/moderate",
        json={"decision": "REJECT", "reason": "الصور غير واضحة"},
        headers=mod_h,
    )
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["status_reason"] == "الصور غير واضحة"

    resubmitted = api.post(f"/api/v1/properties/{listing['id']}/submit", headers=owner_h)
    assert resubmitted.json()["status"] == "PENDING_REVIEW"
    statuses = api.get(f"/api/v1/properties/{listing['id']}/status-history", headers=owner_h).json()
    assert [s["to_status"] for s in statuses] == [
        "DRAFT",
        "PENDING_REVIEW",
        "REJECTED",
        "PENDING_REVIEW",
    ]


def test_moderator_cannot_moderate_own_listing(api: TestClient, place, db_session: Session) -> None:
    mod_owner = make_user(db_session, roles=[Role.MODERATOR, Role.PROPERTY_OWNER])
    headers = auth_headers(api, mod_owner)
    listing = _create(api, headers, place)
    upload_image(api, headers, listing["id"])
    api.post(f"/api/v1/properties/{listing['id']}/submit", headers=headers)
    response = api.post(
        f"/api/v1/properties/{listing['id']}/moderate",
        json={"decision": "APPROVE"},
        headers=headers,
    )
    assert response.json()["error"]["code"] == "CONFLICT_OF_INTEREST"


def test_suspended_listing_is_hidden_and_locked(api: TestClient, owner_h, mod_h, place) -> None:
    listing = _create(api, owner_h, place)
    publish(api, owner_h, mod_h, listing["id"])
    api.post(
        f"/api/v1/properties/{listing['id']}/moderate",
        json={"decision": "SUSPEND", "reason": "بلاغ احتيال قيد التحقق"},
        headers=mod_h,
    )
    assert api.get(f"/api/v1/properties/{listing['id']}").status_code == 404
    locked = api.patch(
        f"/api/v1/properties/{listing['id']}", json={"title_ar": "محاولة تعديل"}, headers=owner_h
    )
    assert locked.json()["error"]["code"] == "LISTING_LOCKED"


def test_sold_and_rented_transitions(api: TestClient, owner_h, mod_h, place) -> None:
    listing = _create(api, owner_h, place)
    publish(api, owner_h, mod_h, listing["id"])
    wrong = api.post(f"/api/v1/properties/{listing['id']}/mark-rented", headers=owner_h)
    assert wrong.status_code == 409
    sold = api.post(f"/api/v1/properties/{listing['id']}/mark-sold", headers=owner_h)
    assert sold.json()["status"] == "SOLD"


def test_unpublish_archive_and_delete(api: TestClient, owner_h, mod_h, place) -> None:
    listing = _create(api, owner_h, place)
    publish(api, owner_h, mod_h, listing["id"])
    assert (
        api.post(f"/api/v1/properties/{listing['id']}/unpublish", headers=owner_h).json()["status"]
        == "DRAFT"
    )
    assert (
        api.post(f"/api/v1/properties/{listing['id']}/archive", headers=owner_h).json()["status"]
        == "ARCHIVED"
    )
    assert api.delete(f"/api/v1/properties/{listing['id']}", headers=owner_h).status_code == 204
    assert api.get(f"/api/v1/properties/{listing['id']}", headers=owner_h).status_code == 404


def test_my_properties_lists_drafts(api: TestClient, owner_h, place) -> None:
    listing = _create(api, owner_h, place)
    page = api.get("/api/v1/me/properties", headers=owner_h).json()
    assert [item["id"] for item in page["items"]] == [listing["id"]]
    assert api.get("/api/v1/me/properties?status=APPROVED", headers=owner_h).json()["total"] == 0


# --------------------------------------------------------------------------- verification


def test_verification_badge_requires_evidence(api: TestClient, owner_h, mod_h, place) -> None:
    listing = _create(api, owner_h, place)
    publish(api, owner_h, mod_h, listing["id"])
    phone_only = api.post(
        f"/api/v1/properties/{listing['id']}/verifications",
        json={"kind": "PHONE", "result": "PASSED"},
        headers=mod_h,
    )
    assert phone_only.status_code == 201
    assert api.get(f"/api/v1/properties/{listing['id']}").json()["verified"] is False

    api.post(
        f"/api/v1/properties/{listing['id']}/verifications",
        json={"kind": "OWNERSHIP", "result": "PASSED", "note": "صك طابو مطابق"},
        headers=mod_h,
    )
    public = api.get(f"/api/v1/properties/{listing['id']}").json()
    assert public["verified"] is True
    records = api.get(f"/api/v1/properties/{listing['id']}/verifications").json()
    assert {r["kind"] for r in records} == {"PHONE", "OWNERSHIP"}
    assert all(r["note"] is None for r in records)  # private notes stay private


def test_owner_cannot_verify_own_listing(api: TestClient, owner_h, place) -> None:
    listing = _create(api, owner_h, place)
    response = api.post(
        f"/api/v1/properties/{listing['id']}/verifications",
        json={"kind": "OWNERSHIP", "result": "PASSED"},
        headers=owner_h,
    )
    assert response.status_code == 403
