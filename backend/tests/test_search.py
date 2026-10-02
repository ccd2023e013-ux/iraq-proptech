"""Search: filters, Arabic keyword matching, sorting, pagination, spatial, favorites."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.rbac.catalog import Role
from tests.factories import (
    BASRA_ASHAR,
    BASRA_CORNICHE,
    auth_headers,
    basra,
    make_district,
    make_listing,
    make_user,
)

pytestmark = pytest.mark.db

SEARCH = "/api/v1/search/properties"
ZUBAIR = (47.7044, 30.3892)  # ~15 km south-west of central Basra
BAGHDAD = (44.3661, 33.3152)


@pytest.fixture
def lister(db_session: Session):
    return make_user(db_session, roles=[Role.PROPERTY_OWNER])


def _ids(response) -> list[str]:
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def test_only_published_listings_are_searchable(
    api: TestClient, db_session: Session, lister
) -> None:
    live = make_listing(db_session, lister)
    make_listing(db_session, lister, status="DRAFT")
    make_listing(db_session, lister, status="PENDING_REVIEW")
    make_listing(db_session, lister, status="SUSPENDED")
    assert _ids(api.get(SEARCH)) == [str(live.id)]


def test_structured_filters(api: TestClient, db_session: Session, lister) -> None:
    house = make_listing(
        db_session,
        lister,
        price_amount=Decimal("200000000"),
        area_m2=Decimal("250"),
        bedrooms=4,
        amenities=["PARKING", "NATIONAL_GRID"],
    )
    apartment = make_listing(
        db_session,
        lister,
        property_type_code="APARTMENT",
        price_amount=Decimal("90000000"),
        area_m2=Decimal("120"),
        bedrooms=2,
        amenities=["ELEVATOR", "PARKING"],
    )
    usd = make_listing(db_session, lister, price_amount=Decimal("150000"), currency="USD")
    rent = make_listing(
        db_session, lister, purpose="RENT", rent_period="MONTHLY", price_amount=Decimal("750000")
    )

    def ids(**params: object) -> set[str]:
        return set(_ids(api.get(SEARCH, params=params)))

    assert ids(purpose="RENT") == {str(rent.id)}
    assert ids(property_types=["APARTMENT"]) == {str(apartment.id)}
    assert ids(property_types=["APARTMENT", "HOUSE"]) >= {str(apartment.id), str(house.id)}
    # Price filters only ever compare within one currency.
    assert ids(currency="IQD", min_price="100000000", max_price="250000000") == {str(house.id)}
    assert ids(currency="USD", max_price="200000") == {str(usd.id)}
    assert ids(min_area="200") == {str(house.id)}
    assert ids(bedrooms_min=4) == {str(house.id)}
    assert ids(amenities=["PARKING"]) == {str(house.id), str(apartment.id)}
    assert ids(amenities=["PARKING", "ELEVATOR"]) == {str(apartment.id)}  # all-of


def test_price_filter_requires_currency(api: TestClient) -> None:
    response = api.get(SEARCH, params={"max_price": "100"})
    assert response.status_code == 422
    assert "currency" in str(response.json()["error"]["details"]).lower()


def test_invalid_ranges_rejected(api: TestClient) -> None:
    assert api.get(SEARCH, params={"min_area": 300, "max_area": 100}).status_code == 422
    assert api.get(SEARCH, params={"sort": "distance"}).status_code == 422
    assert api.get(SEARCH, params={"purpose": "STEAL"}).status_code == 422


def test_verified_demo_and_recency_filters(api: TestClient, db_session: Session, lister) -> None:
    verified = make_listing(db_session, lister, verified_at=datetime.now(UTC))
    demo = make_listing(db_session, lister, is_demo=True)
    old = make_listing(db_session, lister, published_at=datetime.now(UTC) - timedelta(days=60))
    assert set(_ids(api.get(SEARCH, params={"verified_only": True}))) == {str(verified.id)}
    assert str(demo.id) not in _ids(api.get(SEARCH, params={"exclude_demo": True}))
    recent = _ids(api.get(SEARCH, params={"posted_within_days": 30}))
    assert str(old.id) not in recent and str(verified.id) in recent


# --------------------------------------------------------------------------- keywords (Arabic)


def test_arabic_spelling_variants_match(api: TestClient, db_session: Session, lister) -> None:
    taa = make_listing(db_session, lister, title_ar="بيت للبيع في البصره قرب الكورنيش")
    hamza = make_listing(db_session, lister, title_ar="شقة في أربيل")
    assert str(taa.id) in _ids(api.get(SEARCH, params={"q": "البصرة"}))
    assert str(hamza.id) in _ids(api.get(SEARCH, params={"q": "اربيل"}))


def test_keyword_matches_location_names(api: TestClient, db_session: Session, lister) -> None:
    district = make_district(db_session, basra(db_session)[1])  # "العشار"
    in_ashar = make_listing(db_session, lister, title_ar="بيت واسع", district_id=district.id)
    elsewhere = make_listing(db_session, lister, title_ar="بيت واسع آخر")
    found = _ids(api.get(SEARCH, params={"q": "العشار"}))
    assert str(in_ashar.id) in found and str(elsewhere.id) not in found


def test_keyword_by_reference_code(api: TestClient, db_session: Session, lister) -> None:
    listing = make_listing(db_session, lister)
    assert _ids(api.get(SEARCH, params={"q": listing.reference_code})) == [str(listing.id)]


def test_like_wildcards_are_literal(api: TestClient, db_session: Session, lister) -> None:
    make_listing(db_session, lister, title_ar="بيت عادي")
    assert _ids(api.get(SEARCH, params={"q": "%"})) == []
    assert _ids(api.get(SEARCH, params={"q": "_"})) == []


def test_relevance_sort(api: TestClient, db_session: Session, lister) -> None:
    weak = make_listing(db_session, lister, title_ar="أرض", description_ar="قريبة من مسبح عام")
    strong = make_listing(
        db_session, lister, title_ar="فيلا مع مسبح", description_ar="فيلا حديثة مع مسبح خاص كبير"
    )
    ranked = _ids(api.get(SEARCH, params={"q": "مسبح", "sort": "relevance"}))
    assert ranked.index(str(strong.id)) < ranked.index(str(weak.id))


# --------------------------------------------------------------------------- sorting & pagination


def test_sorting_and_pagination(api: TestClient, db_session: Session, lister) -> None:
    prices = [Decimal(p) for p in ("300000000", "100000000", "200000000", "150000000", "250000000")]
    listings = [make_listing(db_session, lister, price_amount=p) for p in prices]
    by_price = [
        str(p.id) for p, _ in sorted(zip(listings, prices, strict=True), key=lambda t: t[1])
    ]
    assert _ids(api.get(SEARCH, params={"sort": "price_asc", "currency": "IQD"})) == by_price
    assert _ids(api.get(SEARCH, params={"sort": "price_desc"})) == by_price[::-1]

    page1 = api.get(SEARCH, params={"sort": "price_asc", "page_size": 2, "page": 1}).json()
    page3 = api.get(SEARCH, params={"sort": "price_asc", "page_size": 2, "page": 3}).json()
    assert page1["total"] == 5
    assert [i["id"] for i in page1["items"]] == by_price[:2]
    assert [i["id"] for i in page3["items"]] == by_price[4:]


def test_price_sort_never_mixes_currencies(api: TestClient, db_session: Session, lister) -> None:
    """Without a currency filter, amounts are grouped by currency, not compared raw."""
    usd = make_listing(db_session, lister, currency="USD", price_amount=Decimal("150000"))
    iqd_low = make_listing(db_session, lister, price_amount=Decimal("100000000"))
    iqd_high = make_listing(db_session, lister, price_amount=Decimal("300000000"))
    assert _ids(api.get(SEARCH, params={"sort": "price_asc"})) == [
        str(iqd_low.id),
        str(iqd_high.id),
        str(usd.id),
    ]
    assert _ids(api.get(SEARCH, params={"sort": "price_desc"})) == [
        str(iqd_high.id),
        str(iqd_low.id),
        str(usd.id),
    ]
    assert _ids(api.get(SEARCH, params={"sort": "price_asc", "currency": "USD"})) == [str(usd.id)]


def test_search_runs_a_constant_number_of_queries(
    api: TestClient, db_session: Session, lister
) -> None:
    for _ in range(12):
        make_listing(db_session, lister, amenities=["PARKING"])
    statements: list[str] = []

    def count(*args: object, **kwargs: object) -> None:
        statements.append(str(args[2]))

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", count)
    try:
        response = api.get(SEARCH, params={"page_size": 12})
    finally:
        event.remove(engine, "before_cursor_execute", count)
    assert len(response.json()["items"]) == 12
    assert len(statements) <= 10, statements  # no N+1: independent of result count


# --------------------------------------------------------------------------- spatial


def test_bbox_radius_and_polygon(api: TestClient, db_session: Session, lister) -> None:
    ashar = make_listing(db_session, lister, point=BASRA_ASHAR, privacy="EXACT")
    zubair = make_listing(db_session, lister, point=ZUBAIR, privacy="EXACT", city_slug="zubair")
    baghdad = make_listing(
        db_session,
        lister,
        point=BAGHDAD,
        privacy="EXACT",
        governorate_code="BGD",
        city_slug="baghdad",
    )
    basra_box = {"bbox": "47.5,30.2,48.1,30.7"}
    assert set(_ids(api.get(SEARCH, params=basra_box))) == {str(ashar.id), str(zubair.id)}

    near = {"near_lat": BASRA_CORNICHE[1], "near_lon": BASRA_CORNICHE[0], "radius_km": 5}
    assert _ids(api.get(SEARCH, params=near)) == [str(ashar.id)]
    wide = _ids(api.get(SEARCH, params={**near, "radius_km": 30, "sort": "distance"}))
    assert wide == [str(ashar.id), str(zubair.id)]

    polygon = "47.80,30.50;47.83,30.50;47.83,30.52;47.80,30.52"
    assert _ids(api.get(SEARCH, params={"polygon": polygon})) == [str(ashar.id)]
    body = {"polygon": [[47.80, 30.50], [47.83, 30.50], [47.83, 30.52], [47.80, 30.52]]}
    assert _ids(api.post(SEARCH, json=body)) == [str(ashar.id)]
    assert str(baghdad.id) in _ids(api.get(SEARCH))
    # a drawn triangle (3 open points, as the map UI sends) is valid
    triangle = "47.79,30.49;47.84,30.49;47.815,30.53"
    assert _ids(api.get(SEARCH, params={"polygon": triangle})) == [str(ashar.id)]
    # degenerate shapes are rejected
    assert api.get(SEARCH, params={"polygon": "47.8,30.5;47.9,30.5;47.8,30.5"}).status_code == 422


def test_hidden_locations_never_appear_in_spatial_results(
    api: TestClient, db_session: Session, lister
) -> None:
    hidden = make_listing(db_session, lister, point=BASRA_ASHAR, privacy="HIDDEN")
    assert _ids(api.get(SEARCH, params={"bbox": "47.5,30.2,48.1,30.7"})) == []
    assert _ids(api.get(SEARCH)) == [str(hidden.id)]


def test_rejects_huge_bbox(api: TestClient) -> None:
    assert api.get(SEARCH, params={"bbox": "-170,-80,170,80"}).status_code == 422


# --------------------------------------------------------------------------- favorites


def test_favorites(api: TestClient, db_session: Session, lister) -> None:
    live = make_listing(db_session, lister)
    draft = make_listing(db_session, lister, status="DRAFT")
    customer = auth_headers(api, make_user(db_session))
    assert api.put(f"/api/v1/properties/{live.id}/favorite", headers=customer).status_code == 204
    assert api.put(f"/api/v1/properties/{live.id}/favorite", headers=customer).status_code == 204
    assert api.put(f"/api/v1/properties/{draft.id}/favorite", headers=customer).status_code == 404
    assert api.get("/api/v1/me/favorites/ids", headers=customer).json() == [str(live.id)]
    page = api.get("/api/v1/me/favorites", headers=customer).json()
    assert page["total"] == 1 and page["items"][0]["id"] == str(live.id)
    assert api.delete(f"/api/v1/properties/{live.id}/favorite", headers=customer).status_code == 204
    assert api.get("/api/v1/me/favorites/ids", headers=customer).json() == []
    assert api.put(f"/api/v1/properties/{live.id}/favorite").status_code == 401
