"""In-process domain events.

Domain code announces what happened (``lead.created``, ``property.approved``,
...) without knowing who listens. Handlers run **inside the caller's
transaction** (so an in-app notification is committed atomically with the
change that caused it); anything with external side effects (email, SMS,
webhooks, n8n) must enqueue work to run after commit — see
``app/notifications``. A failing handler is logged and never breaks the
business operation.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

Handler = Callable[[Session, str, dict[str, Any]], None]
_handlers: dict[str, list[Handler]] = defaultdict(list)


def subscribe(name: str, handler: Handler) -> None:
    """Register ``handler`` for event ``name`` (``*`` receives every event)."""
    if handler not in _handlers[name]:
        _handlers[name].append(handler)


def unsubscribe(name: str, handler: Handler) -> None:
    if handler in _handlers.get(name, []):
        _handlers[name].remove(handler)


def emit(db: Session, name: str, payload: dict[str, Any]) -> None:
    for handler in [*_handlers.get(name, []), *_handlers.get("*", [])]:
        try:
            with db.begin_nested():  # a failing handler rolls back only its own writes
                handler(db, name, payload)
        except Exception:
            logger.exception("event handler failed", extra={"event": name})
