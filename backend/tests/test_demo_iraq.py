"""National DEMO dataset: coverage, labelling, idempotency, accounts, searches."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import demo_iraq
from app.agencies.models import Agency, AgencyMember
from app.geo.models import City
from app.properties.models import Property, PropertyMedia
from app.rbac.catalog import Role
from app.storage import get_storage
from app.users.models import User
from tests.factories import login

pytestmark = pytest.mark.db

PASSWORD = "Demo-Accounts-Pass-2026"
CITY_SLUGS = {"basra", "baghdad", "najaf", "karbala", "erbil", "mosul", "sulaymaniyah"}


def _demo_listings(db: Session) -> list[Property]:
    lister = db.execute(select(User).where(User.email == demo_iraq.LISTER_EMAIL)).scalar_one()
    agent = db.execute(select(User).where(User.email == "demo.agent@example.com")).scalar_one()
    return list(
        db.execute(select(Property).where(Property.lister_id.in_([lister.id, agent.id]))).scalars()
    )


def test_seed_covers_seven_cities_and_is_clearly_demo(db_session: Session) -> None:
    result = demo_iraq.seed(db_session, per_city=4, account_password=PASSWORD)
    assert result["cities"] == 7 and result["listings_created"] == 28

    listings = _demo_listings(db_session)
    assert len(listings) == 28
    city_slugs = {db_session.get(City, p.city_id).slug for p in listings}
    assert city_slugs == CITY_SLUGS
    for p in listings:
        assert p.is_demo and p.status == "APPROVED"
        assert "تجريبي" in p.title_ar and p.title_en.startswith("DEMO")
        assert "ليس عرضاً حقيقياً" in p.description_ar
        assert p.display_location is not None
    # Every demo listing has a generated, stored DEMO illustration.
    media = list(
        db_session.execute(
            select(PropertyMedia).where(PropertyMedia.property_id.in_([p.id for p in listings]))
        ).scalars()
    )
    assert len(media) == 28
    assert all("DEMO" in m.caption for m in media)
    assert get_storage().get(media[0].thumbnail_key)[:4] == b"RIFF"  # WebP
    # Agency listings belong to the verified demo agency and its agent.
    agency = db_session.execute(
        select(Agency).where(Agency.slug == demo_iraq.AGENCY_SLUG)
    ).scalar_one()
    assert agency.status == "VERIFIED"
    assert any(p.agency_id == agency.id for p in listings)


def test_seed_is_idempotent(db_session: Session) -> None:
    demo_iraq.seed(db_session, per_city=3, images=False)
    again = demo_iraq.seed(db_session, per_city=3, images=False)
    assert again["listings_created"] == 0 and again["pois_created"] == 0
    assert len(_demo_listings(db_session)) == 21
    grown = demo_iraq.seed(db_session, per_city=4, images=False)
    assert grown["listings_created"] == 7


def test_demo_accounts_sign_in_with_the_environment_password(
    api: TestClient, db_session: Session
) -> None:
    demo_iraq.seed(db_session, per_city=1, account_password=PASSWORD, images=False)
    for email, _, role in demo_iraq.DEMO_ACCOUNTS:
        tokens = login(api, email, PASSWORD)
        me = api.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access']}"}
        ).json()
        assert me["user"]["email_verified"] is True
        if role is not None:
            assert role.value in me["user"]["roles"]
    agent = db_session.execute(
        select(User).where(User.email == "demo.agent@example.com")
    ).scalar_one()
    assert Role.AGENT in agent.roles
    assert (
        db_session.execute(
            select(func.count()).select_from(AgencyMember).where(AgencyMember.user_id == agent.id)
        ).scalar_one()
        == 1
    )


def test_seed_without_password_creates_no_usable_login(
    api: TestClient, db_session: Session
) -> None:
    demo_iraq.seed(db_session, per_city=1, images=False)
    response = api.post(
        "/api/v1/auth/login", json={"email": "demo.admin@example.com", "password": PASSWORD}
    )
    assert response.status_code == 401


def test_weak_demo_password_is_rejected(db_session: Session) -> None:
    with pytest.raises(ValueError, match="DEMO_ACCOUNT_PASSWORD"):
        demo_iraq.seed(db_session, per_city=1, account_password="short", images=False)


@pytest.mark.parametrize(
    ("query", "purpose", "type_code"),
    [
        ("بيت للبيع في البصرة", "SALE", "HOUSE"),
        ("شقة للإيجار في بغداد", "RENT", "APARTMENT"),
        ("house for sale in Basra", "SALE", "HOUSE"),
    ],
)
def test_canonical_searches_find_demo_listings(
    api: TestClient, db_session: Session, query: str, purpose: str, type_code: str
) -> None:
    demo_iraq.seed(db_session, per_city=4, images=False)
    body = api.get("/api/v1/ai/search", params={"q": query, "page_size": 50}).json()
    filters = body["interpretation"]["result"]["filters"]
    assert filters["purpose"] == purpose
    assert body["total"] >= 1, filters
    for item in body["items"]:
        assert item["purpose"] == purpose and item["property_type_code"] == type_code


def test_ai_compare_uses_declared_facts_and_local_medians(
    api: TestClient, db_session: Session
) -> None:
    from decimal import Decimal

    from app.rbac.catalog import Role
    from tests.factories import make_listing, make_user

    owner = make_user(db_session, roles=[Role.CUSTOMER, Role.PROPERTY_OWNER])
    cheap = make_listing(
        db_session, owner, price_amount=Decimal("150000000"), area_m2=Decimal("300"), bedrooms=4
    )
    dear = make_listing(
        db_session, owner, price_amount=Decimal("300000000"), area_m2=Decimal("200"), bedrooms=3
    )
    for price in ("200000000", "220000000", "240000000"):
        make_listing(db_session, owner, price_amount=Decimal(price), area_m2=Decimal("200"))
    usd = make_listing(db_session, owner, price_amount=Decimal("90000"), currency="USD")
    hidden = make_listing(db_session, owner, status="DRAFT")

    body = api.get("/api/v1/ai/compare", params={"ids": f"{cheap.id},{dear.id}"}).json()
    assert body["provider"] == "platform" and body["feature"] == "property.compare"
    result = body["result"]
    assert result["prices_comparable"] is True
    assert result["highlights"] == {
        "lowest_price_per_m2": str(cheap.id),
        "largest_area": str(cheap.id),
        "most_bedrooms": str(cheap.id),
    }
    first = result["properties"][0]
    assert first["price_per_m2"] == "500000.00" and first["local_median_per_m2"] is not None

    mixed = api.get("/api/v1/ai/compare", params={"ids": f"{cheap.id},{usd.id}"}).json()
    assert mixed["result"]["prices_comparable"] is False
    assert mixed["result"]["highlights"]["lowest_price_per_m2"] is None

    # Unpublished listings stay invisible; bad input is rejected.
    assert (
        api.get("/api/v1/ai/compare", params={"ids": f"{cheap.id},{hidden.id}"}).status_code == 404
    )
    assert (
        api.get("/api/v1/ai/compare", params={"ids": str(cheap.id) + ",x" * 20}).status_code == 422
    )
    assert (
        api.get("/api/v1/ai/compare", params={"ids": f"{cheap.id},{cheap.id}"}).status_code == 422
    )
