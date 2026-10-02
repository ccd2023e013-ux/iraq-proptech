"""GIS: map points and clusters, boundaries, point resolution, admin polygons, demo seed."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import demo
from app.audit.models import AuditLog
from app.geo.models import District
from app.map import service as map_service
from app.properties.models import Property
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

MAP = "/api/v1/map/properties"
BASRA_BOX = "47.5,30.2,48.1,30.7"
# Real Iraqi coordinates (lon, lat)
BAGHDAD_TAHRIR = (44.3958, 33.3317)
ERBIL_CITADEL = (44.0092, 36.1911)
MOSUL = (43.1189, 36.3456)
TEHRAN = (51.389, 35.6892)  # outside Iraq
KUWAIT_CITY = (47.9783, 29.3759)  # inside Iraq's bounding box, but not Iraq

ASHAR_SQUARE = {
    "type": "Polygon",
    "coordinates": [
        [[47.805, 30.500], [47.828, 30.500], [47.828, 30.522], [47.805, 30.522], [47.805, 30.500]]
    ],
}


@pytest.fixture
def lister(db_session: Session):
    return make_user(db_session, roles=[Role.PROPERTY_OWNER])


@pytest.fixture
def admin_headers(api: TestClient, db_session: Session) -> dict[str, str]:
    return auth_headers(api, make_user(db_session, roles=[Role.ADMIN]))


def _features(response) -> list[dict]:
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "FeatureCollection"
    return body["features"]


# --------------------------------------------------------------------------- map points


def test_map_returns_public_points_only(api: TestClient, db_session: Session, lister) -> None:
    exact = make_listing(db_session, lister, point=BASRA_CORNICHE, privacy="EXACT")
    approx = make_listing(db_session, lister, point=BASRA_ASHAR, privacy="APPROXIMATE")
    make_listing(db_session, lister, point=BASRA_ASHAR, privacy="HIDDEN")
    make_listing(db_session, lister, point=BASRA_ASHAR, status="DRAFT")

    features = {f["id"]: f for f in _features(api.get(MAP, params={"bbox": BASRA_BOX}))}
    assert set(features) == {str(exact.id), str(approx.id)}
    assert features[str(exact.id)]["geometry"]["coordinates"] == list(BASRA_CORNICHE)
    approx_coords = features[str(approx.id)]["geometry"]["coordinates"]
    assert approx_coords != list(BASRA_ASHAR)  # coarsened, never the exact point
    assert features[str(approx.id)]["properties"]["approximate"] is True
    props = features[str(exact.id)]["properties"]
    assert props["currency"] == "IQD" and props["price_amount"] == "100000000.00"
    assert "location" not in props and "exact_location" not in props


def test_map_applies_search_filters_and_viewport(
    api: TestClient, db_session: Session, lister
) -> None:
    sale = make_listing(db_session, lister, point=BASRA_CORNICHE, privacy="EXACT")
    make_listing(
        db_session,
        lister,
        point=BASRA_CORNICHE,
        privacy="EXACT",
        purpose="RENT",
        rent_period="MONTHLY",
    )
    make_listing(
        db_session,
        lister,
        point=BAGHDAD_TAHRIR,
        privacy="EXACT",
        governorate_code="BGD",
        city_slug="baghdad",
    )
    ids = [f["id"] for f in _features(api.get(MAP, params={"bbox": BASRA_BOX, "purpose": "SALE"}))]
    assert ids == [str(sale.id)]
    assert len(_features(api.get(MAP))) == 3  # no viewport: whole country


def test_map_clusters_when_dense(
    api: TestClient, db_session: Session, lister, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(map_service, "POINT_LIMIT", 3)
    for dx in range(4):
        make_listing(db_session, lister, point=(47.80 + dx * 0.001, 30.51), privacy="EXACT")
    make_listing(
        db_session,
        lister,
        point=ERBIL_CITADEL,
        privacy="EXACT",
        governorate_code="EBL",
        city_slug="erbil",
    )

    body = api.get(MAP, params={"zoom": 6}).json()
    assert body["meta"]["mode"] == "clusters"
    assert body["meta"]["total"] == 5
    counts = sorted(f["properties"]["point_count"] for f in body["features"])
    assert counts == [1, 4]
    assert all(f["properties"]["cluster"] for f in body["features"])
    # zoomed into a single street the same data is still clustered, in finer cells
    fine = api.get(MAP, params={"zoom": 20}).json()
    assert fine["meta"]["cell_degrees"] < body["meta"]["cell_degrees"]
    assert sum(f["properties"]["point_count"] for f in fine["features"]) == 5


def test_cluster_cell_size_shrinks_with_zoom() -> None:
    sizes = [map_service.cluster_cell_degrees(z) for z in range(0, 23)]
    assert sizes == sorted(sizes, reverse=True)
    assert map_service.cluster_cell_degrees(99) == map_service.cluster_cell_degrees(22)


def test_map_rejects_invalid_filters(api: TestClient) -> None:
    assert api.get(MAP, params={"zoom": 40}).status_code == 422
    assert api.get(MAP, params={"bbox": "1,2,3"}).status_code in (400, 422)


# --------------------------------------------------------------------------- spatial search with Iraqi coordinates


def test_radius_and_polygon_across_iraqi_cities(
    api: TestClient, db_session: Session, lister
) -> None:
    basra_l = make_listing(db_session, lister, point=BASRA_CORNICHE, privacy="EXACT")
    erbil_l = make_listing(
        db_session,
        lister,
        point=ERBIL_CITADEL,
        privacy="EXACT",
        governorate_code="EBL",
        city_slug="erbil",
    )
    mosul_l = make_listing(
        db_session, lister, point=MOSUL, privacy="EXACT", governorate_code="NIN", city_slug="mosul"
    )
    near_erbil = {"near_lat": ERBIL_CITADEL[1], "near_lon": ERBIL_CITADEL[0], "radius_km": 20}
    assert [f["id"] for f in _features(api.get(MAP, params=near_erbil))] == [str(erbil_l.id)]
    # Erbil–Mosul is ~80 km: a 100 km radius around Erbil includes both, not Basra (~600 km)
    wide = {f["id"] for f in _features(api.get(MAP, params={**near_erbil, "radius_km": 100}))}
    assert wide == {str(erbil_l.id), str(mosul_l.id)}
    north = "42.5,35.5;44.5,35.5;44.5,37.0;42.5,37.0"
    assert {f["id"] for f in _features(api.get(MAP, params={"polygon": north}))} == {
        str(erbil_l.id),
        str(mosul_l.id),
    }
    assert str(basra_l.id) not in {
        f["id"] for f in _features(api.get(MAP, params={"polygon": north}))
    }


# --------------------------------------------------------------------------- admin boundaries


def test_admin_creates_district_with_boundary_and_it_resolves(
    api: TestClient, db_session: Session, admin_headers
) -> None:
    _, city = basra(db_session)
    created = api.post(
        "/api/v1/admin/locations/districts",
        headers=admin_headers,
        json={
            "parent_id": str(city.id),
            "name_ar": "العشار",
            "name_en": "Al-Ashar Test",
            "boundary": {"geometry": ASHAR_SQUARE, "source": "Test survey (unit test)"},
        },
    )
    assert created.status_code == 201, created.text
    feature = created.json()
    assert feature["geometry"]["type"] == "MultiPolygon"
    assert feature["properties"]["has_boundary"] is True
    assert feature["properties"]["geometry_source"] == "Test survey (unit test)"
    district_id = feature["id"]

    # centroid derived inside the polygon
    lon, lat = feature["properties"]["centroid"]["lon"], feature["properties"]["centroid"]["lat"]
    assert 47.805 < lon < 47.828 and 30.500 < lat < 30.522

    inside = api.get(
        "/api/v1/locations/resolve", params={"lon": BASRA_ASHAR[0], "lat": BASRA_ASHAR[1]}
    )
    assert inside.status_code == 200
    body = inside.json()
    assert body["method"] == "boundary" and body["approximate"] is False
    assert body["district"]["id"] == district_id
    assert body["city"]["id"] == str(city.id)
    assert body["governorate"]["name_en"] == "Basra"

    listing = api.get(
        "/api/v1/locations/boundaries", params={"level": "districts", "parent_id": str(city.id)}
    )
    assert [f["id"] for f in _features(listing)] == [district_id]

    audit_row = db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "location.created", AuditLog.resource_id == district_id
        )
    ).scalar_one()
    assert audit_row.resource_type == "districts"


def test_resolve_falls_back_to_nearest_city_and_flags_it(api: TestClient) -> None:
    corniche = api.get(
        "/api/v1/locations/resolve", params={"lon": BASRA_CORNICHE[0], "lat": BASRA_CORNICHE[1]}
    ).json()
    assert corniche["method"] == "nearest_city_centroid"
    assert corniche["approximate"] is True
    assert corniche["city"] is not None  # nearest seeded city centroid in Basra governorate
    assert corniche["governorate"]["name_en"] == "Basra"
    assert corniche["district"] is None
    assert 0 < corniche["distance_km"] < 10

    baghdad = api.get(
        "/api/v1/locations/resolve", params={"lon": BAGHDAD_TAHRIR[0], "lat": BAGHDAD_TAHRIR[1]}
    ).json()
    assert baghdad["governorate"]["name_en"] == "Baghdad"

    kuwait = api.get(
        "/api/v1/locations/resolve", params={"lon": KUWAIT_CITY[0], "lat": KUWAIT_CITY[1]}
    ).json()
    assert kuwait["method"] == "none" and kuwait["city"] is None  # never guessed

    outside = api.get("/api/v1/locations/resolve", params={"lon": TEHRAN[0], "lat": TEHRAN[1]})
    assert outside.status_code == 422
    assert outside.json()["error"]["code"] == "OUTSIDE_IRAQ"


@pytest.mark.parametrize(
    ("geometry", "fragment"),
    [
        (  # unclosed ring
            {
                "type": "Polygon",
                "coordinates": [[[47.80, 30.50], [47.82, 30.50], [47.82, 30.52], [47.80, 30.52]]],
            },
            "closed",
        ),
        (  # Tehran
            {
                "type": "Polygon",
                "coordinates": [[[51.3, 35.6], [51.4, 35.6], [51.4, 35.7], [51.3, 35.6]]],
            },
            "inside Iraq",
        ),
        (  # lat/lon swapped (common mistake) → outside Iraq
            {
                "type": "Polygon",
                "coordinates": [[[30.50, 47.80], [30.50, 47.82], [30.52, 47.82], [30.50, 47.80]]],
            },
            "inside Iraq",
        ),
        ({"type": "Point", "coordinates": [47.8, 30.5]}, "Polygon"),
        (
            {
                "type": "Polygon",
                "coordinates": [[[47.8, "30.5"], [47.9, 30.5], [47.9, 30.6], [47.8, 30.5]]],
            },
            "numbers",
        ),
    ],
)
def test_invalid_boundaries_are_rejected(
    api: TestClient, db_session: Session, admin_headers, geometry: dict, fragment: str
) -> None:
    _, city = basra(db_session)
    district = make_district(db_session, city)
    response = api.put(
        f"/api/v1/admin/locations/districts/{district.id}/boundary",
        headers=admin_headers,
        json={"geometry": geometry, "source": "test"},
    )
    assert response.status_code == 422
    assert fragment in response.text


def test_self_intersecting_boundary_is_repaired(
    api: TestClient, db_session: Session, admin_headers
) -> None:
    _, city = basra(db_session)
    district = make_district(db_session, city)
    bowtie = {
        "type": "Polygon",
        "coordinates": [
            [[47.80, 30.50], [47.82, 30.52], [47.82, 30.50], [47.80, 30.52], [47.80, 30.50]]
        ],
    }
    response = api.put(
        f"/api/v1/admin/locations/districts/{district.id}/boundary",
        headers=admin_headers,
        json={"geometry": bowtie, "source": "test"},
    )
    assert response.status_code == 200, response.text
    db_session.expire_all()
    valid = db_session.execute(
        select(func.ST_IsValid(District.boundary)).where(District.id == district.id)
    ).scalar_one()
    assert valid is True

    cleared = api.delete(
        f"/api/v1/admin/locations/districts/{district.id}/boundary", headers=admin_headers
    )
    assert cleared.status_code == 204
    feature = api.get(f"/api/v1/locations/districts/{district.id}/geojson").json()
    assert feature["properties"]["has_boundary"] is False


@pytest.mark.parametrize("role", [Role.CUSTOMER, Role.AGENCY_OWNER, Role.MODERATOR])
def test_only_admins_manage_locations(api: TestClient, db_session: Session, role: Role) -> None:
    _, city = basra(db_session)
    district = make_district(db_session, city)
    headers = auth_headers(api, make_user(db_session, roles=[role]))
    put = api.put(
        f"/api/v1/admin/locations/districts/{district.id}/boundary",
        headers=headers,
        json={"geometry": ASHAR_SQUARE, "source": "x" * 5},
    )
    assert put.status_code == 403
    post = api.post(
        "/api/v1/admin/locations/neighborhoods",
        headers=headers,
        json={"parent_id": str(district.id), "name_ar": "حي", "name_en": "Hay"},
    )
    assert post.status_code == 403
    assert (
        api.delete(
            f"/api/v1/admin/locations/districts/{district.id}/boundary", headers=headers
        ).status_code
        == 403
    )


def test_place_creation_validation(api: TestClient, db_session: Session, admin_headers) -> None:
    _, city = basra(db_session)
    url = "/api/v1/admin/locations/districts"
    base = {"parent_id": str(city.id), "name_ar": "منطقة", "name_en": "Some Area"}
    assert api.post(url, headers=admin_headers, json=base).status_code == 201
    dup = api.post(url, headers=admin_headers, json=base)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "SLUG_TAKEN"
    assert (
        api.post(url, headers=admin_headers, json={**base, "slug": "Bad Slug"}).status_code == 422
    )
    assert (
        api.post(
            url,
            headers=admin_headers,
            json={**base, "slug": "far", "centroid": {"lat": TEHRAN[1], "lon": TEHRAN[0]}},
        ).status_code
        == 422
    )
    assert (
        api.post(
            "/api/v1/admin/locations/governorates", headers=admin_headers, json=base
        ).status_code
        == 422
    )
    missing_parent = {**base, "parent_id": "00000000-0000-0000-0000-000000000000", "slug": "x"}
    assert api.post(url, headers=admin_headers, json=missing_parent).status_code == 404


def test_boundaries_listing_requires_parent_below_city(api: TestClient) -> None:
    assert api.get("/api/v1/locations/boundaries", params={"level": "districts"}).status_code == 422
    assert (
        api.get("/api/v1/locations/boundaries", params={"level": "governorates"}).status_code == 200
    )


def test_place_geojson_without_boundary_returns_centroid(
    api: TestClient, db_session: Session
) -> None:
    gov, _ = basra(db_session)
    feature = api.get(f"/api/v1/locations/governorates/{gov.id}/geojson").json()
    assert feature["geometry"]["type"] == "Point"
    assert feature["properties"]["has_boundary"] is False
    assert (
        api.get(
            "/api/v1/locations/governorates/00000000-0000-0000-0000-000000000000/geojson"
        ).status_code
        == 404
    )


# --------------------------------------------------------------------------- demo seed


def test_demo_seed_is_labelled_idempotent_and_resettable(db_session: Session) -> None:
    first = demo.seed(db_session, listings=12)
    assert first == {
        "listings_created": 12,
        "districts": len(demo.BASRA_DISTRICTS),
        "pois_created": len(demo.BASRA_DISTRICTS) * len(demo._DEMO_POIS),
    }
    again = demo.seed(db_session, listings=12)
    assert again["listings_created"] == 0 and again["pois_created"] == 0

    rows = (
        db_session.execute(select(Property).where(Property.title_ar.like("عقار تجريبي%")))
        .scalars()
        .all()
    )
    assert len(rows) == 12
    assert all(p.is_demo and p.status == "APPROVED" for p in rows)
    assert all("تجريبي" in p.description_ar for p in rows)
    assert all(not p.media for p in rows)  # no invented photos
    assert {p.currency for p in rows} <= {"IQD", "USD"}

    sources = set(
        db_session.execute(
            select(District.geometry_source).where(
                District.slug.in_([d.slug for d in demo.BASRA_DISTRICTS])
            )
        ).scalars()
    )
    assert sources == {demo.DEMO_GEOMETRY_SOURCE}

    # every demo listing's public point lies inside its demo district square
    inside = db_session.execute(
        select(func.count())
        .select_from(Property)
        .join(District, District.id == Property.district_id)
        .where(Property.is_demo.is_(True), func.ST_Covers(District.boundary, Property.location))
    ).scalar_one()
    assert inside == 12

    assert demo.reset(db_session) == {"listings_deleted": 12}
    assert (
        db_session.execute(
            select(func.count()).select_from(Property).where(Property.is_demo.is_(True))
        ).scalar_one()
        == 0
    )


def test_demo_listings_can_be_excluded_from_map(
    api: TestClient, db_session: Session, lister
) -> None:
    demo.seed(db_session, listings=5)
    real = make_listing(db_session, lister, point=BASRA_CORNICHE, privacy="EXACT")
    all_ids = {f["id"] for f in _features(api.get(MAP, params={"bbox": BASRA_BOX}))}
    assert len(all_ids) == 6
    flagged = [
        f for f in _features(api.get(MAP, params={"bbox": BASRA_BOX})) if f["properties"]["is_demo"]
    ]
    assert len(flagged) == 5
    real_only = _features(api.get(MAP, params={"bbox": BASRA_BOX, "exclude_demo": "true"}))
    assert [f["id"] for f in real_only] == [str(real.id)]
