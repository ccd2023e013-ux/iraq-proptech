"""Structured (JSON) logging with request-scoped context.

Sensitive values must never be logged; callers pass only identifiers. As a
safety net, keys that look like secrets are redacted before serialization.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)

_REDACT_KEYS = ("password", "token", "secret", "authorization", "api_key", "cookie")
_STANDARD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()) | {
    "message",
    "asctime",
}


def _redact(key: str, value: Any) -> Any:
    lowered = key.lower()
    if any(marker in lowered for marker in _REDACT_KEYS):
        return "[REDACTED]"
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if (rid := request_id_var.get()) is not None:
            payload["request_id"] = rid
        if (uid := user_id_var.get()) is not None:
            payload["user_id"] = uid
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = _redact(key, value)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO", json_logs: bool = True) -> None:
    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # uvicorn's access log duplicates our request log middleware
    logging.getLogger("uvicorn.access").disabled = True
