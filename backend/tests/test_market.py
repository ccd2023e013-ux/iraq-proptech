"""Public market readings: medians from public listings, honest data class."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.rbac.catalog import Role
from tests.factories import make_listing, make_user

pytestmark = pytest.mark.db


def test_summary_medians_by_segment_and_demo_flag(api: TestClient, db_session: Session) -> None:
    owner = make_user(db_session, roles=[Role.CUSTOMER, Role.PROPERTY_OWNER])
    for price, area in (("100000000", "100"), ("200000000", "100"), ("400000000", "200")):
        make_listing(db_session, owner, price_amount=Decimal(price), area_m2=Decimal(area))
    make_listing(db_session, owner, price_amount=Decimal("90000"), currency="USD", is_demo=True)
    make_listing(db_session, owner, price_amount=Decimal("999000000"), status="DRAFT")

    body = api.get("/api/v1/market/summary").json()
    assert body["data_class"] == "platform" and body["includes_demo"] is True
    iqd = next(s for s in body["segments"] if s["currency"] == "IQD")
    assert iqd["listings"] == 3  # the draft is not public
    assert iqd["median_price"] == "200000000.00"
    assert iqd["median_price_per_m2"] == "2000000.00"
    usd = next(s for s in body["segments"] if s["currency"] == "USD")
    assert usd["listings"] == 1  # currencies are never mixed


def test_cities_ranked_by_public_listings(api: TestClient, db_session: Session) -> None:
    owner = make_user(db_session, roles=[Role.CUSTOMER, Role.PROPERTY_OWNER])
    make_listing(db_session, owner)
    make_listing(db_session, owner)
    make_listing(db_session, owner, governorate_code="BGD", city_slug="baghdad", point=None)
    cities = api.get("/api/v1/market/cities").json()
    assert [c["slug"] for c in cities][:2] == ["basra", "baghdad"]
    assert cities[0]["listings"] == 2 and cities[0]["includes_demo"] is False
    city_id = cities[0]["city_id"]
    summary = api.get("/api/v1/market/summary", params={"city_id": city_id}).json()
    assert summary["listings"] == 2
