"""Database + PostGIS integration tests (run against real PostGIS)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.system.models import SystemSetting

pytestmark = pytest.mark.db

# Two real reference points in Basra (WGS84 lon/lat), ~2.4 km apart.
BASRA_CORNICHE = (47.8417, 30.5160)
BASRA_ASHAR = (47.8160, 30.5090)


def test_postgis_is_installed(db_session: Session) -> None:
    version = db_session.execute(text("SELECT postgis_lib_version()")).scalar_one()
    assert version.split(".")[0] >= "3"


def test_geography_distance_in_metres(db_session: Session) -> None:
    distance = db_session.execute(
        text(
            "SELECT ST_Distance("
            "ST_SetSRID(ST_MakePoint(:lon1, :lat1), 4326)::geography,"
            "ST_SetSRID(ST_MakePoint(:lon2, :lat2), 4326)::geography)"
        ),
        {
            "lon1": BASRA_CORNICHE[0],
            "lat1": BASRA_CORNICHE[1],
            "lon2": BASRA_ASHAR[0],
            "lat2": BASRA_ASHAR[1],
        },
    ).scalar_one()
    assert 2_000 < distance < 3_000


def test_point_in_polygon(db_session: Session) -> None:
    inside = db_session.execute(
        text(
            "SELECT ST_Contains("
            "ST_MakeEnvelope(47.80, 30.50, 47.86, 30.53, 4326),"
            "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))"
        ),
        {"lon": BASRA_CORNICHE[0], "lat": BASRA_CORNICHE[1]},
    ).scalar_one()
    assert inside is True


def test_trigram_extension_available(db_session: Session) -> None:
    similarity = db_session.execute(text("SELECT similarity('البصرة', 'بصرة')")).scalar_one()
    assert similarity > 0.3


def test_system_settings_roundtrip(db_session: Session) -> None:
    db_session.add(SystemSetting(key="test.flag", value={"enabled": True}))
    db_session.flush()
    stored = db_session.get(SystemSetting, "test.flag")
    assert stored is not None
    assert stored.value == {"enabled": True}
    assert stored.created_at is not None


def test_readiness_reports_database_and_postgis(migrated_db: None, client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")
    body = response.json()
    assert response.status_code == 200, body
    assert body["database"]["status"] == "ok"
    assert body["postgis"]["status"] == "ok"
    assert body["status"] in {"ok", "degraded"}
