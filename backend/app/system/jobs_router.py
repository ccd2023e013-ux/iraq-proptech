"""External trigger for maintenance jobs (free hosts without a Celery worker).

Disabled unless ``JOBS_TRIGGER_TOKEN`` is configured; requests must carry the
token in ``X-Jobs-Token`` (compared in constant time). Answers 404 when
disabled or when the token is wrong, so the endpoint is not discoverable.
"""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.workers import registry

router = APIRouter(tags=["system"], include_in_schema=False)


@router.post(
    "/internal/jobs/run",
    dependencies=[Depends(rate_limit("jobs-trigger", limit=30, window=3600))],
)
def run_jobs(
    job: list[str] | None = Query(default=None, max_length=20),
    x_jobs_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    expected = get_settings().jobs_trigger_token
    if not expected or not x_jobs_token or not hmac.compare_digest(x_jobs_token, expected):
        raise NotFoundError("Not found")
    names = job or registry.FREQUENT
    try:
        return {"results": registry.run(db, names)}
    except KeyError as exc:
        raise AppError(f"Unknown job: {exc.args[0]}", code="UNKNOWN_JOB") from exc
