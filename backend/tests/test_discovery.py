"""Saved searches, comparison, POIs / nearby, exchange rates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.rbac.catalog import Role
from app.search import saved as saved_module
from tests.factories import BASRA_ASHAR, BASRA_CORNICHE, auth_headers, make_listing, make_user

pytestmark = pytest.mark.db

ZUBAIR = (47.7044, 30.3892)


@pytest.fixture
def lister(db_session: Session):
    return make_user(db_session, roles=[Role.PROPERTY_OWNER])


@pytest.fixture
def customer_headers(api: TestClient, db_session: Session) -> dict[str, str]:
    return auth_headers(api, make_user(db_session))


# --------------------------------------------------------------------------- saved searches

SAVED = "/api/v1/me/saved-searches"


def test_saved_search_lifecycle(
    api: TestClient, db_session: Session, lister, customer_headers
) -> None:
    created = api.post(
        SAVED,
        headers=customer_headers,
        json={
            "name": "بيوت في البصرة",
            "filters": {"purpose": "SALE", "currency": "IQD", "max_price": "300000000"},
            "alert_frequency": "DAILY",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["filters"]["currency"] == "IQD"
    assert body["new_matches"] == 0
    saved_id = body["id"]

    # a matching listing published afterwards counts as new
    make_listing(db_session, lister, price_amount=Decimal("200000000"))
    make_listing(db_session, lister, price_amount=Decimal("900000000"))  # too expensive
    listed = api.get(SAVED, headers=customer_headers).json()
    assert [s["new_matches"] for s in listed] == [1]

    results = api.get(f"{SAVED}/{saved_id}/results", headers=customer_headers).json()
    assert results["total"] == 1
    # viewing marks them seen
    assert api.get(SAVED, headers=customer_headers).json()[0]["new_matches"] == 0

    patched = api.patch(
        f"{SAVED}/{saved_id}",
        headers=customer_headers,
        json={"alert_frequency": "NONE", "name": "معدّل"},
    )
    assert patched.status_code == 200 and patched.json()["alert_frequency"] == "NONE"
    assert api.delete(f"{SAVED}/{saved_id}", headers=customer_headers).status_code == 204
    assert api.get(SAVED, headers=customer_headers).json() == []


def test_saved_search_validation_ownership_and_limit(
    api: TestClient, db_session: Session, customer_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = api.post(
        SAVED, headers=customer_headers, json={"name": "x", "filters": {"max_price": "5"}}
    )
    assert bad.status_code == 422  # price without currency is rejected like in search
    unknown = api.post(SAVED, headers=customer_headers, json={"name": "x", "filters": {"foo": 1}})
    assert unknown.status_code == 422

    mine = api.post(SAVED, headers=customer_headers, json={"name": "a", "filters": {}}).json()
    other = auth_headers(api, make_user(db_session))
    assert api.get(f"{SAVED}/{mine['id']}/results", headers=other).status_code == 404
    assert api.patch(f"{SAVED}/{mine['id']}", headers=other, json={"name": "z"}).status_code == 404
    assert api.delete(f"{SAVED}/{mine['id']}", headers=other).status_code == 404
    assert api.get(SAVED).status_code == 401

    monkeypatch.setattr(saved_module, "MAX_SAVED_SEARCHES", 1)
    over = api.post(SAVED, headers=customer_headers, json={"name": "b", "filters": {}})
    assert over.status_code == 409
    assert over.json()["error"]["code"] == "SAVED_SEARCH_LIMIT"


# --------------------------------------------------------------------------- comparison


def test_compare_listings(api: TestClient, db_session: Session, lister) -> None:
    a = make_listing(
        db_session,
        lister,
        price_amount=Decimal("150000000"),
        area_m2=Decimal("150"),
        amenities=["PARKING", "GARDEN"],
    )
    b = make_listing(
        db_session,
        lister,
        price_amount=Decimal("300000000"),
        area_m2=Decimal("200"),
        bedrooms=5,
        amenities=["PARKING"],
    )
    response = api.get("/api/v1/properties/compare", params={"ids": f"{a.id},{b.id}"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert [i["id"] for i in body["items"]] == [str(a.id), str(b.id)]
    assert body["price_per_m2"] == ["1000000.00", "1500000.00"]
    assert body["same_currency"] is True
    assert body["cheapest_per_m2_id"] == str(a.id)
    assert body["amenities_common"] == ["PARKING"]
    rows = {r["field"]: r for r in body["rows"]}
    assert rows["bedrooms"]["differs"] is True
    assert rows["currency"]["differs"] is False


def test_compare_never_ranks_across_currencies(
    api: TestClient, db_session: Session, lister
) -> None:
    iqd = make_listing(db_session, lister)
    usd = make_listing(db_session, lister, currency="USD", price_amount=Decimal("100000"))
    body = api.get("/api/v1/properties/compare", params={"ids": f"{iqd.id},{usd.id}"}).json()
    assert body["same_currency"] is False
    assert body["cheapest_per_m2_id"] is None


def test_compare_rejects_bad_input_and_private_listings(
    api: TestClient, db_session: Session, lister
) -> None:
    live = make_listing(db_session, lister)
    draft = make_listing(db_session, lister, status="DRAFT")
    url = "/api/v1/properties/compare"
    assert api.get(url, params={"ids": str(live.id)}).status_code == 422
    assert api.get(url, params={"ids": "nope,also-nope"}).status_code == 422
    assert api.get(url, params={"ids": f"{live.id},{draft.id}"}).status_code == 404
    many = ",".join(str(make_listing(db_session, lister).id) for _ in range(5))
    assert api.get(url, params={"ids": many}).status_code == 422


# --------------------------------------------------------------------------- POIs and nearby


def _poi(api, headers, category, lon, lat, name="مدرسة"):
    response = api.post(
        "/api/v1/admin/pois",
        headers=headers,
        json={
            "category": category,
            "name_ar": name,
            "lat": lat,
            "lon": lon,
            "source": "Unit test fixture",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_pois_and_nearby(api: TestClient, db_session: Session, lister) -> None:
    admin = auth_headers(api, make_user(db_session, roles=[Role.ADMIN]))
    school = _poi(api, admin, "SCHOOL", BASRA_CORNICHE[0] + 0.002, BASRA_CORNICHE[1])
    _poi(api, admin, "HOSPITAL", BASRA_CORNICHE[0], BASRA_CORNICHE[1] + 0.004, "مستشفى")
    _poi(api, admin, "SCHOOL", ZUBAIR[0], ZUBAIR[1], "بعيدة")  # ~17 km away

    listing = make_listing(db_session, lister, point=BASRA_CORNICHE, privacy="EXACT")
    nearby = api.get(f"/api/v1/properties/{listing.id}/nearby", params={"radius_m": 1000})
    assert nearby.status_code == 200
    body = nearby.json()
    assert body["available"] is True and body["approximate"] is False
    assert set(body["by_category"]) == {"SCHOOL", "HOSPITAL"}
    first_school = body["by_category"]["SCHOOL"][0]
    assert first_school["id"] == school["id"]
    assert 150 < first_school["distance_m"] < 250  # 0.002° lon at 30.5°N ≈ 192 m
    assert body["total"] == 2

    in_box = api.get("/api/v1/pois", params={"bbox": "47.80,30.48,47.90,30.56"}).json()
    assert len(in_box) == 2
    only_hospitals = api.get(
        "/api/v1/pois", params={"bbox": "47.80,30.48,47.90,30.56", "category": "HOSPITAL"}
    ).json()
    assert [p["category"] for p in only_hospitals] == ["HOSPITAL"]
    assert api.get("/api/v1/pois", params={"bbox": "40,29,48,37"}).status_code == 422

    audit_row = db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "poi.created", AuditLog.resource_id == school["id"]
        )
    ).scalar_one()
    assert audit_row is not None


def test_nearby_respects_location_privacy(api: TestClient, db_session: Session, lister) -> None:
    hidden = make_listing(db_session, lister, point=BASRA_ASHAR, privacy="HIDDEN")
    approx = make_listing(db_session, lister, point=BASRA_ASHAR, privacy="APPROXIMATE")
    draft = make_listing(db_session, lister, point=BASRA_ASHAR, status="DRAFT")
    assert api.get(f"/api/v1/properties/{hidden.id}/nearby").json()["available"] is False
    assert api.get(f"/api/v1/properties/{approx.id}/nearby").json()["approximate"] is True
    assert api.get(f"/api/v1/properties/{draft.id}/nearby").status_code == 404


def test_nearby_properties(api: TestClient, db_session: Session, lister) -> None:
    centre = make_listing(db_session, lister, point=BASRA_CORNICHE, privacy="EXACT")
    close = make_listing(
        db_session, lister, point=(BASRA_CORNICHE[0] + 0.003, BASRA_CORNICHE[1]), privacy="EXACT"
    )
    closer = make_listing(
        db_session, lister, point=(BASRA_CORNICHE[0] + 0.001, BASRA_CORNICHE[1]), privacy="EXACT"
    )
    make_listing(db_session, lister, point=ZUBAIR, privacy="EXACT")  # far
    make_listing(db_session, lister, point=BASRA_CORNICHE, privacy="EXACT", status="DRAFT")
    make_listing(db_session, lister, point=BASRA_CORNICHE, privacy="HIDDEN")
    body = api.get(f"/api/v1/properties/{centre.id}/nearby-properties").json()
    assert [i["id"] for i in body["items"]] == [str(closer.id), str(close.id)]
    assert body["distances_m"][str(closer.id)] < body["distances_m"][str(close.id)]


def test_poi_admin_permissions_and_validation(api: TestClient, db_session: Session) -> None:
    payload = {"category": "PARK", "name_ar": "حديقة", "lat": 30.5, "lon": 47.8, "source": "test"}
    for role in (Role.CUSTOMER, Role.MODERATOR, Role.AGENCY_OWNER):
        headers = auth_headers(api, make_user(db_session, roles=[role]))
        assert api.post("/api/v1/admin/pois", headers=headers, json=payload).status_code == 403
    admin = auth_headers(api, make_user(db_session, roles=[Role.ADMIN]))
    outside = {**payload, "lat": 35.69, "lon": 51.39}  # Tehran
    assert api.post("/api/v1/admin/pois", headers=admin, json=outside).status_code == 422
    bad_category = {**payload, "category": "CASINO"}
    assert api.post("/api/v1/admin/pois", headers=admin, json=bad_category).status_code == 422
    imported = api.post(
        "/api/v1/admin/pois/import",
        headers=admin,
        json={"items": [payload, {**payload, "name_ar": "حديقة 2", "lat": 30.51}]},
    )
    assert imported.status_code == 201 and imported.json() == {"imported": 2}
    # all-or-nothing: one invalid item rejects the batch
    rejected = api.post(
        "/api/v1/admin/pois/import", headers=admin, json={"items": [payload, outside]}
    )
    assert rejected.status_code == 422
    pois = api.get("/api/v1/pois", params={"bbox": "47.7,30.4,47.9,30.6"}).json()
    assert len(pois) == 2
    assert api.delete(f"/api/v1/admin/pois/{pois[0]['id']}", headers=admin).status_code == 204


# --------------------------------------------------------------------------- exchange rates


def test_exchange_rates_are_data_not_constants(api: TestClient, db_session: Session) -> None:
    assert api.get("/api/v1/exchange-rates/latest").json() is None
    none = api.get(
        "/api/v1/exchange-rates/convert", params={"amount": "100", "from": "USD", "to": "IQD"}
    ).json()
    assert none["converted"] is None and "No exchange rate" in none["note"]

    superadmin = auth_headers(api, make_user(db_session, roles=[Role.SUPER_ADMIN]))
    admin = auth_headers(api, make_user(db_session, roles=[Role.ADMIN]))
    rate = {"base": "USD", "quote": "IQD", "rate": "1310.5", "source": "Test bank"}
    assert api.post("/api/v1/admin/exchange-rates", headers=admin, json=rate).status_code == 403
    created = api.post("/api/v1/admin/exchange-rates", headers=superadmin, json=rate)
    assert created.status_code == 201, created.text

    latest = api.get("/api/v1/exchange-rates/latest").json()
    assert latest["rate"] == "1310.500000" and latest["source"] == "Test bank"
    converted = api.get(
        "/api/v1/exchange-rates/convert", params={"amount": "1000", "from": "USD", "to": "IQD"}
    ).json()
    assert converted["converted"] == "1310500" and converted["indicative"] is True
    inverse = api.get(
        "/api/v1/exchange-rates/latest", params={"base": "IQD", "quote": "USD"}
    ).json()
    assert Decimal(inverse["rate"]) == (Decimal(1) / Decimal("1310.5")).quantize(
        Decimal("0.000001")
    )

    # a future-dated rate is not used yet; a newer past rate wins
    future = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    api.post(
        "/api/v1/admin/exchange-rates",
        headers=superadmin,
        json={**rate, "rate": "1500", "effective_at": future},
    )
    assert api.get("/api/v1/exchange-rates/latest").json()["rate"] == "1310.500000"
    bad = api.post(
        "/api/v1/admin/exchange-rates", headers=superadmin, json={**rate, "quote": "USD"}
    )
    assert bad.status_code == 422
    assert (
        api.post(
            "/api/v1/admin/exchange-rates", headers=superadmin, json={**rate, "rate": "0"}
        ).status_code
        == 422
    )


def test_search_never_converts_even_with_a_rate(
    api: TestClient, db_session: Session, lister
) -> None:
    superadmin = auth_headers(api, make_user(db_session, roles=[Role.SUPER_ADMIN]))
    api.post(
        "/api/v1/admin/exchange-rates",
        headers=superadmin,
        json={"rate": "1300", "source": "Test bank"},
    )
    usd = make_listing(db_session, lister, currency="USD", price_amount=Decimal("100000"))
    found = api.get(
        "/api/v1/search/properties",
        params={"currency": "IQD", "min_price": "1", "max_price": "999999999999"},
    ).json()
    assert str(usd.id) not in [i["id"] for i in found["items"]]
