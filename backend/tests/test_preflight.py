"""Deployment preflight checks."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.preflight import config_findings, database_findings

STRONG = "s" * 48


def _codes(**env: str) -> set[str]:
    return {f.code for f in config_findings(Settings.model_validate(env))}


def test_development_defaults_are_clean() -> None:
    assert _codes() == set()


def test_unconfigured_providers_are_errors() -> None:
    codes = _codes(ai_provider="claude", sms_provider="http", storage_backend="s3")
    assert {"AI_KEY_MISSING", "SMS_GATEWAY_MISSING", "S3_BUCKET_MISSING"} <= codes


def test_production_rules() -> None:
    findings = config_findings(
        Settings(
            app_env="production",
            jwt_secret=STRONG,
            cors_origins=["*", "http://evil.example", "http://localhost:3000"],
            cookie_secure=False,
        )
    )
    errors = {f.code for f in findings if f.level == "error"}
    warnings = {f.code for f in findings if f.level == "warning"}
    assert {"CORS_WILDCARD", "CORS_INSECURE_ORIGIN", "COOKIES_NOT_SECURE"} <= errors
    assert {"EMAIL_MOCK", "STORAGE_LOCAL", "DB_DEFAULT_PASSWORD"} <= warnings
    # demo payments are forced off in production unless opted in
    assert "PAYMENTS_DEMO" not in warnings


def test_clean_production_configuration_has_no_errors() -> None:
    findings = config_findings(
        Settings(
            app_env="production",
            jwt_secret=STRONG,
            cors_origins=["https://proptech.example"],
            frontend_url="https://proptech.example",
            database_url="postgresql://app:secret@db:5432/proptech",
        )
    )
    assert not [f for f in findings if f.level == "error"]


@pytest.mark.db
def test_database_preflight_passes_on_migrated_database(migrated_db: None) -> None:
    assert database_findings() == []


# --------------------------------------------------------------------------- jobs trigger

TOKEN = "t" * 40


@pytest.mark.db
def test_jobs_trigger_is_hidden_without_token(api, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "jobs_trigger_token", None)
    assert api.post("/api/v1/internal/jobs/run", headers={"X-Jobs-Token": TOKEN}).status_code == 404


@pytest.mark.db
def test_jobs_trigger_runs_registered_jobs(api, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings
    from app.workers import registry

    monkeypatch.setattr(get_settings(), "jobs_trigger_token", TOKEN)
    assert (
        api.post("/api/v1/internal/jobs/run", headers={"X-Jobs-Token": "x" * 40}).status_code == 404
    )
    ok = api.post("/api/v1/internal/jobs/run", headers={"X-Jobs-Token": TOKEN})
    assert ok.status_code == 200, ok.text
    results = ok.json()["results"]
    assert [r["job"] for r in results] == registry.FREQUENT
    assert all(r["status"] == "SUCCEEDED" for r in results), results
    one = api.post(
        "/api/v1/internal/jobs/run?job=expire_listings", headers={"X-Jobs-Token": TOKEN}
    ).json()
    assert [r["job"] for r in one["results"]] == ["expire_listings"]
    bad = api.post("/api/v1/internal/jobs/run?job=drop_tables", headers={"X-Jobs-Token": TOKEN})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "UNKNOWN_JOB"


def test_malformed_s3_endpoint_and_weak_demo_password_are_flagged(monkeypatch) -> None:
    from app.core.config import Settings
    from app.core.preflight import config_findings

    settings = Settings.model_validate(
        {
            "storage_backend": "s3",
            "s3_bucket": "media",
            "s3_endpoint_url": "https://x.storage.supabase.co/storage/v1/s3](https://x.storage.supabase.co/storage/v1/s3)",
        }
    )
    monkeypatch.setenv("DEMO_ACCOUNT_PASSWORD", "short")
    codes = {f.code for f in config_findings(settings)}
    assert {"S3_ENDPOINT_MALFORMED", "DEMO_PASSWORD_REJECTED"} <= codes
    good = Settings.model_validate(
        {
            "storage_backend": "s3",
            "s3_bucket": "media",
            "s3_endpoint_url": "https://x.storage.supabase.co/storage/v1/s3",
        }
    )
    monkeypatch.setenv("DEMO_ACCOUNT_PASSWORD", "A-Strong-Demo-Pass-1")
    codes = {f.code for f in config_findings(good)}
    assert not {"S3_ENDPOINT_MALFORMED", "DEMO_PASSWORD_REJECTED"} & codes
