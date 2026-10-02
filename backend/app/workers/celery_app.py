"""Celery application.

Run with::

    celery -A app.workers.celery_app worker --loglevel=INFO

The broker is whatever ``REDIS_URL`` points at (container, Codespace, or the
production PC). Business-critical state always lives in PostgreSQL; tasks are
idempotent and safe to retry.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings
from app.db import models as _models  # noqa: F401  (register all tables)

settings = get_settings()

celery_app = Celery("proptech", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Baghdad",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)
celery_app.autodiscover_tasks(["app.workers"])


@celery_app.task(name="system.ping")
def ping() -> str:
    """Smoke-test task used by health checks and CI."""
    return "pong"
