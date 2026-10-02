"""Browser session cookies and CSRF protection.

Browsers authenticate with httpOnly cookies (JavaScript can never read the
tokens). Because cookies are sent automatically, every *unsafe* request
authenticated by cookie must also carry ``X-CSRF-Token`` equal to the
readable ``csrf_token`` cookie (double-submit), on top of SameSite=Lax.
Bearer-token clients (mobile apps, integrations) are not affected.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from fastapi import Request, Response

from app.auth.security import tokens_equal
from app.core.config import get_settings
from app.core.errors import PermissionDeniedError

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _max_age(expires_at: datetime) -> int:
    return max(0, int((expires_at - datetime.now(UTC)).total_seconds()))


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    access_expires_at: datetime,
    refresh_token: str,
    refresh_expires_at: datetime,
) -> None:
    settings = get_settings()

    def put(name: str, value: str, expires_at: datetime, *, httponly: bool) -> None:
        response.set_cookie(
            name,
            value,
            max_age=_max_age(expires_at),
            httponly=httponly,
            secure=settings.secure_cookies,
            samesite="lax",
            domain=settings.cookie_domain,
            path="/",
        )

    put(ACCESS_COOKIE, access_token, access_expires_at, httponly=True)
    put(REFRESH_COOKIE, refresh_token, refresh_expires_at, httponly=True)
    # Readable by the web app's JavaScript so it can echo it in X-CSRF-Token.
    put(CSRF_COOKIE, secrets.token_urlsafe(32), refresh_expires_at, httponly=False)


def clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(
            name,
            path="/",
            domain=settings.cookie_domain,
            secure=settings.secure_cookies,
            httponly=name != CSRF_COOKIE,
            samesite="lax",
        )


def enforce_csrf(request: Request) -> None:
    if request.method in SAFE_METHODS:
        return
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    if not cookie or not header or not tokens_equal(cookie, header):
        raise PermissionDeniedError("Missing or invalid CSRF token", code="CSRF_FAILED")
