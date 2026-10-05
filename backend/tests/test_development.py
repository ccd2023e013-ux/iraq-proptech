"""Development Intelligence: provenance rules, curated import, public API."""

from __future__ import annotations

import copy
import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.development import service
from app.development.models import DevelopmentProject
from app.rbac.catalog import Role
from tests.factories import auth_headers, make_listing, make_user

CURATED = json.loads((service.DATA_DIR / "basra.json").read_text(encoding="utf-8"))


def _record(**changes: object) -> dict:
    record = copy.deepcopy(CURATED["projects"][0])
    record.update(changes)
    return record


def test_curated_records_pass_the_provenance_rules() -> None:
    for record in CURATED["projects"]:
        service.validate_project(record)
        assert all(e["url"].startswith("https://") for e in record["evidence"])
    keys = {s["key"] for s in CURATED["sources"]}
    assert all(e["source"] in keys for p in CURATED["projects"] for e in p["evidence"])


@pytest.mark.parametrize(
    "changes",
    [
        {"evidence": []},
        {"evidence": [{"source": "gcpi", "url": "http://insecure.example", "supports": "STATUS"}]},
        {"lon": 30.0, "lat": 30.0},
        {"location_precision": "APPROXIMATE", "location_note": None},
        {"category": "SPACEPORT"},
        {
            # a timeline without evidence for it
            "evidence": [
                {"source": "gcpi", "url": "https://example.gov.iq/x", "supports": "LOCATION"}
            ]
        },
    ],
)
def test_records_without_provenance_are_rejected(changes: dict) -> None:
    with pytest.raises(service.ProvenanceError):
        service.validate_project(_record(**changes))


@pytest.mark.db
def test_import_is_idempotent_and_served_with_sources(api: TestClient, db_session: Session) -> None:
    first = service.import_dataset(db_session, "basra")
    assert first["created"] == len(CURATED["projects"]) and first["updated"] == 0
    again = service.import_dataset(db_session, "basra")
    assert again["created"] == 0 and again["updated"] == len(CURATED["projects"])

    body = api.get("/api/v1/development/projects").json()
    assert body["type"] == "FeatureCollection"
    slugs = {f["properties"]["slug"] for f in body["features"]}
    assert "basra-grand-faw-port" in slugs
    for feature in body["features"]:
        props = feature["properties"]
        assert props["sources"], "every project names its sources"
        assert props["confidence"] in ("HIGH", "MEDIUM", "LOW")
        assert props["location_precision"] in ("EXACT", "APPROXIMATE", "AREA")

    port = next(f for f in body["features"] if f["properties"]["slug"] == "basra-grand-faw-port")
    detail = api.get(f"/api/v1/development/projects/{port['id']}").json()
    assert detail["status"] == "TRIAL_OPERATION"
    statuses = [e for e in detail["evidence"] if e["supports"] == "STATUS"]
    assert statuses and statuses[0]["source"]["kind"] == "OFFICIAL"
    assert statuses[0]["published_on"] == "2026-01-05"

    water = api.get("/api/v1/development/projects", params={"category": "WATER"}).json()
    assert [f["properties"]["category"] for f in water["features"]] == ["WATER"]
    far = api.get("/api/v1/development/projects", params={"bbox": "43,33,44,34"}).json()
    assert far["features"] == []

    with_evidence = api.get("/api/v1/development/projects", params={"evidence": "true"}).json()
    assert all(f["properties"]["evidence"] for f in with_evidence["features"])

    sources = api.get("/api/v1/development/sources").json()
    assert {s["kind"] for s in sources} >= {"OFFICIAL"}


@pytest.mark.db
def test_unpublished_projects_are_not_served(api: TestClient, db_session: Session) -> None:
    service.import_dataset(db_session, "basra")
    port = db_session.execute(
        select(DevelopmentProject).where(DevelopmentProject.slug == "basra-grand-faw-port")
    ).scalar_one()
    port.is_published = False
    db_session.flush()
    body = api.get("/api/v1/development/projects").json()
    assert "basra-grand-faw-port" not in {f["properties"]["slug"] for f in body["features"]}
    assert api.get(f"/api/v1/development/projects/{port.id}").status_code == 404


@pytest.mark.db
def test_import_requires_permission(api: TestClient, db_session: Session) -> None:
    customer = make_user(db_session, roles=[Role.CUSTOMER])
    admin = make_user(db_session, roles=[Role.ADMIN])
    denied = api.post("/api/v1/admin/development/import", headers=auth_headers(api, customer))
    assert denied.status_code == 403
    ok = api.post("/api/v1/admin/development/import", headers=auth_headers(api, admin))
    assert ok.status_code == 200, ok.text
    assert ok.json()["dataset"] == "basra"


@pytest.mark.db
def test_property_intelligence_cites_nearby_projects(api: TestClient, db_session: Session) -> None:
    service.import_dataset(db_session, "basra")
    owner = make_user(db_session, roles=[Role.PROPERTY_OWNER])
    # A listing in Al-Faw, a few km from the port records.
    listing = make_listing(
        db_session, owner, point=(48.47, 29.97), privacy="EXACT", area_m2=Decimal("300")
    )
    report = api.get(f"/api/v1/ai/properties/{listing.id}/report").json()
    nearby = [s for s in report["statements"] if s["key"] == "source.development_nearby"]
    assert nearby, report["statements"]
    assert all(s["kind"] == "SOURCE" and s["section"] == "development" for s in nearby)
    assert any("Ports of Iraq" in s["source"] for s in nearby)
    assert "development_signals" not in report["gaps"]
