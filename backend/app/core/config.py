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
    # Server-side prepared statements break behind PgBouncer-style *transaction*
    # poolers (e.g. Supabase port 6543). None = auto: disabled when the URL
    # points at port 6543 or carries `pgbouncer=true`.
    db_prepared_statements: bool | None = None

    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = _INSECURE_DEFAULT_SECRET
    jwt_access_ttl_minutes: int = Field(default=15, ge=1, le=24 * 60)
    jwt_refresh_ttl_days: int = Field(default=30, ge=1, le=365)
    jwt_issuer: str = "iraq-proptech"
    jwt_audience: str = "iraq-proptech-api"

    # Browser session cookies. None → Secure only in production (HTTPS).
    cookie_secure: bool | None = None
    cookie_domain: str | None = None

    # Public URL of the web app, used to build links in emails.
    frontend_url: str = "http://localhost:3000"

    email_verification_ttl_hours: int = Field(default=48, ge=1, le=24 * 14)
    password_reset_ttl_minutes: int = Field(default=30, ge=5, le=24 * 60)

    rate_limit_enabled: bool = True
    # Reverse proxies in front of the frontend that append to X-Forwarded-For
    # (TLS proxy / tunnel / platform edge). 0 = never trust the header.
    trusted_proxy_hops: int = Field(default=0, ge=0, le=5)

    # Notifications: "mock" logs messages and keeps them in an in-memory outbox.
    email_provider: Literal["mock", "smtp"] = "mock"
    email_from: str = "Iraq PropTech <no-reply@iraq-proptech.local>"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = True

    # Object storage: "local" (filesystem) or "s3" (MinIO, Supabase Storage, R2, S3...).
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_path: str = "./storage"
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None
    s3_region: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    # Upload limits (bytes)
    max_image_bytes: int = 10 * 1024 * 1024
    max_document_bytes: int = 15 * 1024 * 1024
    max_video_bytes: int = 100 * 1024 * 1024
    max_media_per_property: int = 40

    # SMS: "mock" records deliveries only; "http" posts {to, text} to a gateway.
    sms_provider: Literal["mock", "http"] = "mock"
    sms_gateway_url: str | None = None
    sms_gateway_token: str | None = None

    # Webhooks (n8n and other automation). Private hosts (e.g. http://n8n:5678 on the
    # same Docker network) must be allowed explicitly; production defaults are strict.
    webhook_allow_http: bool = False
    webhook_allow_private_hosts: bool = False

    # Deliver notifications/webhooks right after commit in the API process (useful when
    # no Celery worker runs, e.g. on a free single-container host).
    notifications_inline: bool = False

    # Analytics day boundaries (minutes from UTC). Iraq is UTC+3 with no DST.
    analytics_utc_offset_minutes: int = Field(default=180, ge=-720, le=840)

    # AI: "mock" is deterministic, offline and free (default). Real providers need a key.
    ai_provider: Literal["mock", "claude", "openai", "gemini"] = "mock"
    ai_model: str | None = None  # provider default when unset
    ai_timeout_seconds: float = Field(default=30, gt=0, le=120)
    ai_max_output_tokens: int = Field(default=1200, ge=64, le=8000)
    ai_daily_limit_per_user: int = Field(default=100, ge=0)  # generative calls; 0 = unlimited
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None

    # Payments: "demo" simulates checkout (no money moves, everything flagged DEMO);
    # "none" disables billing. In production demo payments need an explicit opt-in.
    payment_provider: Literal["demo", "none"] = "demo"
    payment_demo_in_production: bool = False

    # External scheduler trigger for worker-less hosts (POST /api/v1/internal/jobs/run
    # with header X-Jobs-Token). Unset = endpoint disabled (404).
    jobs_trigger_token: str | None = Field(default=None, min_length=32)

    # Development helpers such as the mock outbox endpoint. Forced off in production.
    dev_tools_enabled: bool = True

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @field_validator("s3_endpoint_url")
    @classmethod
    def _normalize_s3_endpoint(cls, value: str | None) -> str | None:
        """Tolerate common paste mistakes: no scheme, quotes, a "NAME=" prefix."""
        if value is None or not value.strip():
            return None
        value = value.strip()
        # Also a pasted "S3_ENDPOINT_URL=https://..." line (name copied into the value).
        if value.upper().startswith("S3_ENDPOINT_URL="):
            value = value.split("=", 1)[1].strip()
        value = value.strip("\"'").rstrip("/")
        return value if "://" in value else f"https://{value}"

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

    @property
    def use_prepared_statements(self) -> bool:
        if self.db_prepared_statements is not None:
            return self.db_prepared_statements
        url = self.database_url.lower()
        return ":6543/" not in url and "pgbouncer=true" not in url

    @property
    def secure_cookies(self) -> bool:
        return self.is_production if self.cookie_secure is None else self.cookie_secure

    @property
    def dev_tools(self) -> bool:
        """Development-only endpoints (e.g. mock outbox). Never available in production."""
        return self.dev_tools_enabled and not self.is_production

    @property
    def effective_payment_provider(self) -> str:
        if (
            self.payment_provider == "demo"
            and self.is_production
            and not self.payment_demo_in_production
        ):
            return "none"
        return self.payment_provider


@lru_cache
def get_settings() -> Settings:
    return Settings()
