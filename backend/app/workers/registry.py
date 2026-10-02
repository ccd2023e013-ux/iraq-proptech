"""Named maintenance jobs, independent of the scheduler that runs them.

Celery beat runs them on the production PC; on a worker-less free host an
external scheduler (e.g. a GitHub Actions cron) calls the token-protected
``POST /api/v1/internal/jobs/run`` endpoint, and operators can run them with
``python -m app.cli run-jobs``. Every job is idempotent.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.notifications import jobs, service
from app.search.saved import AlertFrequency

JobFn = Callable[[Session], dict[str, Any]]


def _purge_visitors(db: Session) -> dict[str, Any]:
    from app.analytics.service import purge_visitors

    return purge_visitors(db)


def _expire_subscriptions(db: Session) -> dict[str, Any]:
    from app.billing.service import expire_subscriptions

    return expire_subscriptions(db)


def _deliver(db: Session) -> dict[str, Any]:
    return {
        "notifications": service.process_deliveries(db),
        "webhooks": service.process_webhooks(db),
    }


JOBS: dict[str, JobFn] = {
    "deliver_outbox": _deliver,
    "saved_search_alerts.instant": lambda db: jobs.saved_search_alerts(db, AlertFrequency.INSTANT),
    "saved_search_alerts.daily": lambda db: jobs.saved_search_alerts(db, AlertFrequency.DAILY),
    "saved_search_alerts.weekly": lambda db: jobs.saved_search_alerts(db, AlertFrequency.WEEKLY),
    "reminders": jobs.reminders,
    "expire_listings": jobs.expire_listings,
    "expire_subscriptions": _expire_subscriptions,
    "purge_analytics_visitors": _purge_visitors,
}

# Safe to run on every external tick (each is due-aware or cheap).
FREQUENT = [
    "deliver_outbox",
    "saved_search_alerts.instant",
    "saved_search_alerts.daily",
    "saved_search_alerts.weekly",
    "reminders",
    "expire_listings",
    "expire_subscriptions",
    "purge_analytics_visitors",
]


def run(db: Session, names: list[str]) -> list[dict[str, Any]]:
    unknown = [n for n in names if n not in JOBS]
    if unknown:
        raise KeyError(", ".join(unknown))
    results = []
    for name in names:
        job = service.run_job(db, name, JOBS[name])
        results.append(
            {"job": name, "status": job.status, "detail": job.detail, "error": job.error}
        )
    return results
