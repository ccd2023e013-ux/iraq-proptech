from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth.schemas import Locale, UserOut
from app.rbac.catalog import Role
from app.users.validation import normalize_iraqi_phone


class ProfileUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    preferred_locale: Locale | None = None
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return normalize_iraqi_phone(value)


class SuspendIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class AdminUserOut(UserOut):
    last_login_at: datetime | None
    suspension_reason: str | None


class RoleOut(BaseModel):
    code: Role
    name_ar: str
    name_en: str
    rank: int
    permissions: list[str]


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    occurred_at: datetime
    actor_user_id: uuid.UUID | None
    action: str
    resource_type: str | None
    resource_id: str | None
    ip_address: str | None
    request_id: str | None
    data: dict[str, object]
