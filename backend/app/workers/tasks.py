"""Celery tasks and the beat schedule. Every task is idempotent and safe to retry."""

from __future__ import annotations

from typing import Any

from celery.schedules import crontab

from app.db.session import get_sessionmaker
from app.notifications import jobs, service
from app.search.saved import AlertFrequency
from app.workers.celery_app import celery_app


def _run(name: str, fn: Any) -> dict[str, Any]:
    with get_sessionmaker()() as db:
        job = service.run_job(db, name, fn)
        return {"status": job.status, "detail": job.detail}


@celery_app.task(name="notifications.deliver")
def deliver() -> dict[str, Any]:
    with get_sessionmaker()() as db:
        return {
            "notifications": service.process_deliveries(db),
            "webhooks": service.process_webhooks(db),
        }


@celery_app.task(name="jobs.saved_search_alerts")
def saved_search_alerts(frequency: str) -> dict[str, Any]:
    freq = AlertFrequency(frequency)
    return _run(
        f"saved_search_alerts.{freq.value.lower()}", lambda db: jobs.saved_search_alerts(db, freq)
    )


@celery_app.task(name="jobs.reminders")
def reminders() -> dict[str, Any]:
    return _run("reminders", jobs.reminders)


@celery_app.task(name="jobs.expire_listings")
def expire_listings() -> dict[str, Any]:
    return _run("expire_listings", jobs.expire_listings)


celery_app.conf.beat_schedule = {
    "deliver-outbox": {"task": "notifications.deliver", "schedule": 60.0},
    "saved-search-instant": {
        "task": "jobs.saved_search_alerts",
        "schedule": 600.0,
        "args": ("INSTANT",),
    },
    "saved-search-daily": {
        "task": "jobs.saved_search_alerts",
        "schedule": crontab(hour=6, minute=0),
        "args": ("DAILY",),
    },
    "saved-search-weekly": {
        "task": "jobs.saved_search_alerts",
        "schedule": crontab(hour=6, minute=30, day_of_week=6),
        "args": ("WEEKLY",),
    },
    "reminders": {"task": "jobs.reminders", "schedule": 300.0},
    "expire-listings": {"task": "jobs.expire_listings", "schedule": crontab(minute=15)},
}
