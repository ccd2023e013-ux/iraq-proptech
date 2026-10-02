"""Liveness / readiness endpoints.

* ``/health``        — process is up (no dependencies touched). Used by
                        container orchestrators and free hosts' health checks.
* ``/health/ready``  — database reachable and PostGIS installed; Redis reported
                        but optional, so the API keeps serving when only the
                        background-job layer is down.
"""

from __future__ import annotations

import logging
import os
from typing import Literal

import redis
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import get_settings
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["system"])

CheckStatus = Literal["ok", "error", "unavailable"]


class LivenessOut(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str
    environment: str
    # Deployed git commit when the host provides it (Render: RENDER_GIT_COMMIT).
    commit: str | None = None


class DependencyCheck(BaseModel):
    status: CheckStatus
    detail: str | None = None


class ReadinessOut(BaseModel):
    status: Literal["ok", "degraded", "error"]
    database: DependencyCheck
    postgis: DependencyCheck
    redis: DependencyCheck


@router.get("", response_model=LivenessOut)
def liveness() -> LivenessOut:
    settings = get_settings()
    commit = os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("GIT_COMMIT")
    return LivenessOut(
        service=settings.app_name,
        version=__version__,
        environment=settings.app_env,
        commit=commit[:40] if commit else None,
    )


def _check_database(db: Session) -> tuple[DependencyCheck, DependencyCheck]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("readiness_db_failed", extra={"error_type": type(exc).__name__})
        return (
            DependencyCheck(status="error", detail="database unreachable"),
            DependencyCheck(status="unavailable"),
        )
    try:
        version = db.execute(text("SELECT postgis_lib_version()")).scalar_one()
        return DependencyCheck(status="ok"), DependencyCheck(status="ok", detail=str(version))
    except SQLAlchemyError:
        db.rollback()
        return DependencyCheck(status="ok"), DependencyCheck(
            status="error", detail="PostGIS extension not installed"
        )


def _check_redis() -> DependencyCheck:
    try:
        client = redis.Redis.from_url(
            get_settings().redis_url, socket_connect_timeout=1, socket_timeout=1
        )
        client.ping()
        return DependencyCheck(status="ok")
    except redis.RedisError:
        return DependencyCheck(status="unavailable", detail="redis unreachable (optional)")


@router.get(
    "/ready",
    response_model=ReadinessOut,
    responses={503: {"model": ReadinessOut}},
)
def readiness(response: Response, db: Session = Depends(get_db)) -> ReadinessOut:
    database, postgis = _check_database(db)
    redis_check = _check_redis()
    if database.status != "ok" or postgis.status != "ok":
        overall: Literal["ok", "degraded", "error"] = "error"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif redis_check.status != "ok":
        overall = "degraded"
    else:
        overall = "ok"
    return ReadinessOut(status=overall, database=database, postgis=postgis, redis=redis_check)
