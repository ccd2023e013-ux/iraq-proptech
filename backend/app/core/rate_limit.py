"""Fixed-window rate limiting.

Redis-backed so limits hold across processes and workers; if Redis is
unreachable it degrades to a per-process in-memory window rather than
failing requests (availability over strictness for a dev/free setup).
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections.abc import Callable
from functools import lru_cache

import redis
from fastapi import Request

from app.core.client_ip import client_ip as resolve_client_ip_for
from app.core.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


class RateLimitedError(AppError):
    status_code = 429
    code = "RATE_LIMITED"


class _MemoryWindow:
    def __init__(self) -> None:
        self._counts: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, window: int) -> int:
        now = time.monotonic()
        with self._lock:
            count, reset_at = self._counts.get(key, (0, now + window))
            if now >= reset_at:
                count, reset_at = 0, now + window
            count += 1
            self._counts[key] = (count, reset_at)
            if len(self._counts) > 10_000:  # bound memory
                self._counts = {k: v for k, v in self._counts.items() if v[1] > now}
            return count


class RateLimiter:
    def __init__(self, redis_url: str) -> None:
        self._redis = redis.Redis.from_url(
            redis_url, socket_connect_timeout=0.5, socket_timeout=0.5
        )
        self._memory = _MemoryWindow()

    def hit(self, key: str, window: int) -> int:
        bucket = f"rl:{key}:{int(time.time() // window)}"
        try:
            pipe = self._redis.pipeline()
            pipe.incr(bucket)
            pipe.expire(bucket, window + 1)
            count, _ = pipe.execute()
            return int(count)
        except redis.RedisError:
            return self._memory.hit(key, window)

    def check(self, key: str, *, limit: int, window: int) -> None:
        if self.hit(key, window) > limit:
            raise RateLimitedError(
                "Too many requests, try again later", details={"retry_after_seconds": window}
            )


@lru_cache
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_settings().redis_url)


def client_ip(request: Request) -> str:
    return resolve_client_ip_for(request)


def _digest(value: str) -> str:
    # Keys never contain raw emails/IPs, so Redis holds no personal data.
    return hashlib.sha256(value.encode()).hexdigest()[:32]


def rate_limit(scope: str, *, limit: int, window: int) -> Callable[[Request], None]:
    """FastAPI dependency limiting requests per client IP for ``scope``."""

    def dependency(request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        get_rate_limiter().check(
            f"{scope}:ip:{_digest(client_ip(request))}", limit=limit, window=window
        )

    return dependency


def limit_identifier(scope: str, identifier: str, *, limit: int, window: int) -> None:
    """Additional limit keyed on an identifier such as an email address."""
    if not get_settings().rate_limit_enabled:
        return
    get_rate_limiter().check(
        f"{scope}:id:{_digest(identifier.lower())}", limit=limit, window=window
    )
