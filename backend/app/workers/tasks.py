"""Celery tasks and the beat schedule. Every task is idempotent and safe to retry."""

from __future__ import annotations

from typing import Any

from celery.schedules import crontab

from app.db.session import get_sessionmaker
from app.search.saved import AlertFrequency
from app.workers import registry
from app.workers.celery_app import celery_app


def _run(name: str) -> dict[str, Any]:
    with get_sessionmaker()() as db:
        result = registry.run(db, [name])[0]
        return {"status": result["status"], "detail": result["detail"]}


@celery_app.task(name="notifications.deliver")
def deliver() -> dict[str, Any]:
    # The outbox is polled every minute; not recorded as a job run (too noisy).
    with get_sessionmaker()() as db:
        return registry.JOBS["deliver_outbox"](db)


@celery_app.task(name="jobs.saved_search_alerts")
def saved_search_alerts(frequency: str) -> dict[str, Any]:
    return _run(f"saved_search_alerts.{AlertFrequency(frequency).value.lower()}")


@celery_app.task(name="jobs.reminders")
def reminders() -> dict[str, Any]:
    return _run("reminders")


@celery_app.task(name="jobs.expire_listings")
def expire_listings() -> dict[str, Any]:
    return _run("expire_listings")


@celery_app.task(name="jobs.purge_analytics_visitors")
def purge_analytics_visitors() -> dict[str, Any]:
    return _run("purge_analytics_visitors")


@celery_app.task(name="jobs.expire_subscriptions")
def expire_subscriptions() -> dict[str, Any]:
    return _run("expire_subscriptions")


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
    "purge-analytics-visitors": {
        "task": "jobs.purge_analytics_visitors",
        "schedule": crontab(hour=1, minute=5),
    },
    "expire-subscriptions": {"task": "jobs.expire_subscriptions", "schedule": crontab(minute=20)},
    "expire-listings": {"task": "jobs.expire_listings", "schedule": crontab(minute=15)},
}
