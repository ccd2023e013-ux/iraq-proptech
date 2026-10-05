"""OpenStreetMap place import: parsing, safety limits and idempotent upserts."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.geo import osm
from app.geo.pois import PointOfInterest

BASRA = osm.CITY_BBOXES["basra"]


def _elements() -> list[dict[str, Any]]:
    return [
        {
            "type": "node",
            "id": 1,
            "lat": 30.51,
            "lon": 47.80,
            "tags": {"amenity": "school", "name": "مدرسة البصرة"},
        },
        {
            "type": "way",
            "id": 2,
            "center": {"lat": 30.52, "lon": 47.81},
            "tags": {"amenity": "hospital", "name": "Basra Hospital", "name:ar": "مستشفى البصرة"},
        },
        {
            "type": "node",
            "id": 3,
            "lat": 30.53,
            "lon": 47.82,
            "tags": {"amenity": "place_of_worship", "religion": "muslim", "name": "جامع"},
        },
        # Skipped: no name / unknown religion / unsupported tag / outside the bbox.
        {"type": "node", "id": 4, "lat": 30.5, "lon": 47.8, "tags": {"amenity": "pharmacy"}},
        {
            "type": "node",
            "id": 5,
            "lat": 30.5,
            "lon": 47.8,
            "tags": {"amenity": "place_of_worship", "name": "x"},
        },
        {
            "type": "node",
            "id": 6,
            "lat": 30.5,
            "lon": 47.8,
            "tags": {"shop": "bakery", "name": "y"},
        },
        {
            "type": "node",
            "id": 7,
            "lat": 33.3,
            "lon": 44.4,
            "tags": {"amenity": "school", "name": "Baghdad school"},
        },
    ]


def test_parse_classifies_names_and_filters() -> None:
    places = {p.external_ref: p for p in osm.parse(_elements(), BASRA)}
    assert set(places) == {"osm:node/1", "osm:way/2", "osm:node/3"}
    assert places["osm:node/1"].category == "SCHOOL"
    assert places["osm:node/1"].name_ar == "مدرسة البصرة"
    assert places["osm:node/1"].name_en is None
    hospital = places["osm:way/2"]
    assert (hospital.category, hospital.name_ar, hospital.name_en) == (
        "HOSPITAL",
        "مستشفى البصرة",
        "Basra Hospital",
    )
    assert (hospital.lon, hospital.lat) == (47.81, 30.52)
    assert places["osm:node/3"].category == "MOSQUE"


def test_parse_strips_control_and_bidi_characters() -> None:
    element = {
        "type": "node",
        "id": 9,
        "lat": 30.5,
        "lon": 47.8,
        "tags": {"amenity": "bank", "name": "Bank‮\u0007 of Basra"},
    }
    (place,) = osm.parse([element], BASRA)
    assert place.name_en == "Bank of Basra"


@pytest.mark.parametrize(
    "bbox",
    [
        (47.9, 30.4, 47.7, 30.6),  # reversed
        (30.0, 30.0, 30.1, 30.1),  # outside Iraq
        (44.0, 32.0, 46.0, 34.0),  # too large
    ],
)
def test_bbox_is_validated(bbox: osm.Bbox) -> None:
    with pytest.raises(ValueError):
        osm.validate_bbox(bbox)


def test_query_is_bounded() -> None:
    query = osm.overpass_query(BASRA)
    assert query.startswith("[out:json][timeout:120];")
    assert "(30.4,47.7,30.62,47.92)" in query
    assert f"out center tags {osm.MAX_ITEMS};" in query


def test_import_is_idempotent_and_deactivates_removed_places(
    api: TestClient, db_session: Session
) -> None:
    first = osm.import_places(db_session, city_slug="basra", fetcher=lambda _bbox: _elements())
    assert (first["created"], first["updated"], first["deactivated"]) == (3, 0, 0)
    assert first["source"] == osm.OSM_SOURCE

    again = osm.import_places(db_session, city_slug="basra", fetcher=lambda _bbox: _elements()[:2])
    assert (again["created"], again["updated"], again["deactivated"]) == (0, 2, 1)

    rows = {
        p.external_ref: p
        for p in db_session.execute(
            select(PointOfInterest).where(PointOfInterest.external_ref.like("osm:%"))
        ).scalars()
    }
    assert rows["osm:node/3"].is_active is False
    assert all(not p.is_demo and p.source == osm.OSM_SOURCE for p in rows.values())

    # Public API shows real places with their attribution.
    pois = api.get("/api/v1/pois", params={"bbox": ",".join(map(str, BASRA))}).json()
    osm_pois = [p for p in pois if p["source"] == osm.OSM_SOURCE]
    assert {p["name_ar"] for p in osm_pois} == {"مدرسة البصرة", "مستشفى البصرة"}


def test_dry_run_writes_nothing(db_session: Session) -> None:
    result = osm.import_places(
        db_session, city_slug="basra", fetcher=lambda _bbox: _elements(), dry_run=True
    )
    assert result["found"] == 3
    assert result["by_category"] == {"SCHOOL": 1, "HOSPITAL": 1, "MOSQUE": 1}
    count = db_session.execute(
        select(PointOfInterest).where(PointOfInterest.external_ref.like("osm:%"))
    ).all()
    assert count == []
