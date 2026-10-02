"""Reference data: Iraqi locations, property types, amenities; app startup."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.mark.db
def test_all_iraqi_governorates_are_seeded(api: TestClient) -> None:
    rows = api.get("/api/v1/locations/governorates").json()
    assert len(rows) == 19
    by_code = {r["code"]: r for r in rows}
    assert by_code["BSR"]["name_ar"] == "البصرة"
    assert by_code["BSR"]["centroid"]["lat"] == pytest.approx(30.5085, abs=1e-4)
    assert {"BGD", "NJF", "KRB", "EBL", "SUL", "NIN"} <= set(by_code)


@pytest.mark.db
def test_cities_by_governorate(api: TestClient) -> None:
    gov = next(g for g in api.get("/api/v1/locations/governorates").json() if g["code"] == "BSR")
    cities = api.get("/api/v1/locations/cities", params={"governorate_id": gov["id"]}).json()
    slugs = {c["slug"] for c in cities}
    assert {"basra", "zubair", "qurnah", "umm-qasr"} <= slugs
    assert all(c["parent_id"] == gov["id"] for c in cities)
    assert all("Approximate" in (c["geometry_source"] or "") for c in cities)


@pytest.mark.db
def test_reference_lists(api: TestClient) -> None:
    types = api.get("/api/v1/reference/property-types").json()
    assert types[0]["code"] == "APARTMENT"
    amenities = {a["code"] for a in api.get("/api/v1/reference/amenities").json()}
    assert {"GENERATOR_SUBSCRIPTION", "NATIONAL_GRID", "SOLAR_PANELS"} <= amenities


def test_fresh_process_configures_all_mappers() -> None:
    """Regression: a new API process must register every ORM model (see Phase 2 report)."""
    code = (
        "from app.main import app\n"
        "from sqlalchemy.orm import configure_mappers\n"
        "configure_mappers()\n"
        "from app.db.base import Base\n"
        "assert 'roles' in Base.metadata.tables and 'properties' in Base.metadata.tables\n"
    )
    result = subprocess.run(  # noqa: S603 - fixed arguments
        [sys.executable, "-c", code], cwd=BACKEND_DIR, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.db
def test_cli_creates_superadmin_in_a_fresh_process(migrated_db: None) -> None:
    """Regression: the CLI must register all models too (found by the Docker smoke test)."""
    import os
    import uuid

    from sqlalchemy import delete, select

    from app.db.session import get_sessionmaker
    from app.users.models import User

    email = f"cli-{uuid.uuid4().hex[:8]}@example.com"
    env = {**os.environ, "SUPERADMIN_PASSWORD": "Cli-Admin-Pass-2026"}
    result = subprocess.run(  # noqa: S603 - fixed arguments
        [sys.executable, "-m", "app.cli", "create-superadmin", "--email", email],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    with get_sessionmaker()() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        assert "SUPER_ADMIN" in {r.value for r in user.roles}
        db.execute(delete(User).where(User.id == user.id))  # committed outside the test txn
        db.commit()
