"""Deployment preflight: catch unsafe or inconsistent configuration before start.

Used by ``python -m app.cli preflight`` (run by deploy platforms before the
API starts, and by CI). Findings are ``error`` (refuse to start in production)
or ``warning`` (works, but probably not what you want). The checks only read
configuration; ``--db`` additionally verifies the database (PostGIS present,
migrations at head).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

from app.core.config import Settings
from app.users.validation import password_problems

Level = Literal["error", "warning"]


@dataclass(frozen=True)
class Finding:
    level: Level
    code: str
    message: str


def _is_local(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def config_findings(settings: Settings) -> list[Finding]:
    out: list[Finding] = []
    prod = settings.is_production

    def add(level: Level, code: str, message: str) -> None:
        out.append(Finding(level, code, message))

    # Providers must be fully configured whatever the environment.
    key_for = {
        "claude": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "gemini": settings.gemini_api_key,
    }
    if settings.ai_provider in key_for and not key_for[settings.ai_provider]:
        add("error", "AI_KEY_MISSING", f"AI_PROVIDER={settings.ai_provider} needs its API key")
    if settings.sms_provider == "http" and not settings.sms_gateway_url:
        add("error", "SMS_GATEWAY_MISSING", "SMS_PROVIDER=http needs SMS_GATEWAY_URL")
    if settings.email_provider == "smtp" and not settings.smtp_host:
        add("error", "SMTP_HOST_MISSING", "EMAIL_PROVIDER=smtp needs SMTP_HOST")
    if settings.storage_backend == "s3" and not settings.s3_bucket:
        add("error", "S3_BUCKET_MISSING", "STORAGE_BACKEND=s3 needs S3_BUCKET")
    if settings.s3_endpoint_url:
        endpoint = urlparse(settings.s3_endpoint_url)
        if (
            endpoint.scheme not in ("http", "https")
            or not endpoint.hostname
            or any(c in settings.s3_endpoint_url for c in " []()<>")
        ):
            # e.g. pasted as a markdown link "https://x/s3](https://x/s3)"
            add("warning", "S3_ENDPOINT_MALFORMED", "S3_ENDPOINT_URL is not a plain URL")
    demo_password = os.environ.get("DEMO_ACCOUNT_PASSWORD")
    if demo_password and password_problems(demo_password):
        add(
            "warning",
            "DEMO_PASSWORD_REJECTED",
            "DEMO_ACCOUNT_PASSWORD fails the password policy; demo seeding will stop",
        )
    admin_password = os.environ.get("DEMO_ADMIN_PASSWORD")
    if admin_password and (password_problems(admin_password) or admin_password == demo_password):
        add(
            "warning",
            "DEMO_ADMIN_PASSWORD_REJECTED",
            "DEMO_ADMIN_PASSWORD fails the password policy or equals DEMO_ACCOUNT_PASSWORD; "
            "demo seeding will stop",
        )

    if not prod:
        return out

    for origin in settings.cors_origins:
        if origin == "*":
            add("error", "CORS_WILDCARD", "CORS_ORIGINS must list origins explicitly in production")
        elif origin.startswith("http://") and not _is_local(origin):
            add("error", "CORS_INSECURE_ORIGIN", f"CORS origin {origin} is not https")
    if not settings.secure_cookies:
        add("error", "COOKIES_NOT_SECURE", "COOKIE_SECURE must not be false in production")
    if settings.frontend_url.startswith("http://") and not _is_local(settings.frontend_url):
        add("warning", "FRONTEND_URL_HTTP", "FRONTEND_URL is not https (email links)")
    if "proptech:proptech@" in settings.database_url:
        add("warning", "DB_DEFAULT_PASSWORD", "DATABASE_URL uses the development password")
    if not settings.rate_limit_enabled:
        add("warning", "RATE_LIMIT_DISABLED", "RATE_LIMIT_ENABLED=false in production")
    if settings.email_provider == "mock":
        add("warning", "EMAIL_MOCK", "EMAIL_PROVIDER=mock: verification/reset emails are not sent")
    if settings.storage_backend == "local":
        add(
            "warning",
            "STORAGE_LOCAL",
            "STORAGE_BACKEND=local: STORAGE_LOCAL_PATH must be a persistent volume",
        )
    if settings.webhook_allow_http or settings.webhook_allow_private_hosts:
        add(
            "warning",
            "WEBHOOK_RELAXED",
            "Webhook SSRF guard relaxed (only for n8n on the same private network)",
        )
    if settings.effective_payment_provider == "demo":
        add("warning", "PAYMENTS_DEMO", "DEMO payments are enabled on a production deployment")
    return out


def database_findings() -> list[Finding]:
    """Live checks: PostGIS available and the schema migrated to head."""
    from pathlib import Path

    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import text

    from app.db.session import get_engine

    out: list[Finding] = []
    backend_dir = Path(__file__).resolve().parents[2]
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    heads = set(ScriptDirectory.from_config(cfg).get_heads())
    try:
        with get_engine().connect() as conn:
            version = conn.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'postgis'")
            ).scalar_one_or_none()
            current = set(MigrationContext.configure(conn).get_current_heads())
    except Exception as exc:
        return [Finding("error", "DB_UNREACHABLE", f"{type(exc).__name__}: database check failed")]
    if not version:
        out.append(Finding("error", "POSTGIS_MISSING", "PostGIS is not installed"))
    if current != heads:
        out.append(
            Finding(
                "error",
                "MIGRATIONS_PENDING",
                f"database at {sorted(current) or 'empty'}, code at {sorted(heads)}",
            )
        )
    return out
