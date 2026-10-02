"""Consistent API error envelope.

Every error response has the shape::

    {"error": {"code": "PROPERTY_NOT_FOUND", "message": "...", "details": ...,
               "request_id": "..."}}

``code`` is a stable machine-readable identifier the frontend maps to a
friendly Arabic/English message; ``message`` is an English developer message.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_var

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for expected, user-facing errors."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "BAD_REQUEST"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "PERMISSION_DENIED"


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "NOT_AUTHENTICATED"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"


_HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "NOT_AUTHENTICATED",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    429: "RATE_LIMITED",
}


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    if (rid := request_id_var.get()) is not None:
        body["request_id"] = rid
    return {"error": body}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=error_body(exc.code, exc.message, exc.details)
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"loc": list(err.get("loc", [])), "msg": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,  # constant name differs across Starlette versions
            content=error_body("VALIDATION_ERROR", "Request validation failed", details),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", extra={"error_type": type(exc).__name__})
        _record_error_event(request, exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body("INTERNAL_ERROR", "An unexpected error occurred"),
        )


def _record_error_event(request: Request, exc: Exception) -> None:
    """Best effort: keep a minimal record for the admin error log (never raises)."""
    try:
        from app.core.logging import user_id_var
        from app.db.session import get_sessionmaker
        from app.moderation.models import ErrorEvent

        uid = user_id_var.get()
        with get_sessionmaker()() as db:
            db.add(
                ErrorEvent(
                    # The request context may already be reset when this handler runs
                    # (outermost middleware); fall back to the validated inbound header.
                    request_id=request_id_var.get() or _safe_request_id(request),
                    method=request.method,
                    path=request.url.path[:300],
                    error_type=type(exc).__name__[:120],
                    user_id=uuid.UUID(uid) if uid else None,
                )
            )
            db.commit()
    except Exception:  # pragma: no cover - the error log must never cause a second failure
        logger.warning("error_event_not_recorded")


def _safe_request_id(request: Request) -> str | None:
    value = request.headers.get("x-request-id", "")
    return (
        value
        if value and len(value) <= 64 and value.replace("-", "").replace("_", "").isalnum()
        else None
    )
