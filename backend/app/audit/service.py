"""Write audit events inside the caller's transaction.

Because the audit row is added to the same session as the change it
describes, both commit (or roll back) together — there are no audited actions
that did not happen, and no unaudited ones that did.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.core.logging import client_ip_var, request_id_var, user_agent_var

_FORBIDDEN_KEYS = ("password", "token", "secret", "hash")


def _clean(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {}
    cleaned = {}
    for key, value in data.items():
        if any(marker in key.lower() for marker in _FORBIDDEN_KEYS):
            continue  # defence in depth: never persist credentials in the audit log
        cleaned[key] = value if isinstance(value, str | int | float | bool | None) else str(value)
    return cleaned


def record(
    db: Session,
    action: str,
    *,
    actor_id: uuid.UUID | None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | str | None = None,
    data: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        action=action,
        actor_user_id=actor_id,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        ip_address=client_ip_var.get(),
        user_agent=user_agent_var.get(),
        request_id=request_id_var.get(),
        data=_clean(data),
    )
    db.add(entry)
    return entry
