import pytest
from pydantic import ValidationError

from app.core.config import Settings, normalize_database_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgres://u:p@h:5432/d", "postgresql+psycopg://u:p@h:5432/d"),
        ("postgresql://u:p@h/d?sslmode=require", "postgresql+psycopg://u:p@h/d?sslmode=require"),
        ("postgresql+psycopg2://u:p@h/d", "postgresql+psycopg://u:p@h/d"),
        ("postgresql+psycopg://u:p@h/d", "postgresql+psycopg://u:p@h/d"),
    ],
)
def test_database_url_is_normalized(raw: str, expected: str) -> None:
    assert normalize_database_url(raw) == expected


def test_cors_origins_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, https://b.test ,")
    assert Settings().cors_origins == ["http://a.test", "https://b.test"]


def test_production_rejects_default_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValidationError):
        Settings()


def test_production_accepts_strong_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 48)
    assert Settings().is_production


def test_production_hides_openapi_and_dev_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import create_app

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 48)
    app = create_app(Settings())
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/v1/openapi.json" not in paths
    assert "/docs" not in paths
    assert not any(p.startswith("/api/v1/dev") for p in paths)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgresql://u:p@db:5432/d", True),
        ("postgresql://u:p@aws-0-x.pooler.supabase.com:6543/postgres", False),
        ("postgresql://u:p@host:5432/d?pgbouncer=true", False),
    ],
)
def test_prepared_statements_auto_detect_transaction_poolers(
    monkeypatch: pytest.MonkeyPatch, url: str, expected: bool
) -> None:
    monkeypatch.setenv("DATABASE_URL", url)
    assert Settings().use_prepared_statements is expected
    monkeypatch.setenv("DB_PREPARED_STATEMENTS", "true")
    assert Settings().use_prepared_statements is True
