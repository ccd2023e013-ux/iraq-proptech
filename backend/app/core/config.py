"""Application settings, loaded from environment variables (12-factor).

Nothing here is specific to a hosting provider: the same image runs on a laptop,
in GitHub Codespaces, on a temporary free host, or on the production PC.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_INSECURE_DEFAULT_SECRET = "change-me-in-every-environment"  # noqa: S105 - sentinel, not a secret


def normalize_database_url(url: str) -> str:
    """Force the psycopg (v3) SQLAlchemy driver regardless of how the URL was written.

    Hosted providers (Supabase, Render, ...) hand out ``postgres://`` or
    ``postgresql://`` URLs; we accept them as-is so no provider-specific config
    is needed.
    """
    for prefix in ("postgres://", "postgresql://", "postgresql+psycopg2://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


class Settings(BaseSettings):
    # Repo-root .env (monorepo) then backend/.env; real environment variables win over both.
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), extra="ignore", case_sensitive=False
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Iraq PropTech"
    log_level: str = "INFO"
    log_json: bool = True

    database_url: str = "postgresql+psycopg://proptech:proptech@localhost:5432/proptech"
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=5, ge=0, le=50)

    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = _INSECURE_DEFAULT_SECRET
    jwt_access_ttl_minutes: int = Field(default=15, ge=1, le=24 * 60)
    jwt_refresh_ttl_days: int = Field(default=30, ge=1, le=365)

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("jwt_secret")
    @classmethod
    def _reject_default_secret_in_production(cls, value: str, info: object) -> str:
        data = getattr(info, "data", {}) or {}
        if data.get("app_env") == "production" and (
            value == _INSECURE_DEFAULT_SECRET or len(value) < 32
        ):
            raise ValueError("JWT_SECRET must be set to a strong value (>= 32 chars) in production")
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
