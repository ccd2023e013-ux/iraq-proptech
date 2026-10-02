from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.rbac.catalog import SELF_SERVICE_ROLES, Role
from app.users.models import User
from app.users.validation import normalize_iraqi_phone

Locale = Literal["ar", "en"]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    full_name: str = Field(min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    account_type: Role = Role.CUSTOMER
    locale: Locale = "ar"

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return normalize_iraqi_phone(value)

    @field_validator("account_type")
    @classmethod
    def _self_service(cls, value: Role) -> Role:
        if value not in SELF_SERVICE_ROLES:
            raise ValueError("Only CUSTOMER or PROPERTY_OWNER can be chosen at registration")
        return value

    @field_validator("full_name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Name is too short")
        return value


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class RefreshIn(BaseModel):
    refresh_token: str | None = Field(default=None, max_length=200)


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=1, max_length=256)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    phone: str | None
    full_name: str
    preferred_locale: str
    status: str
    email_verified: bool
    phone_verified_at: datetime | None
    created_at: datetime
    roles: list[Role]


class MeOut(BaseModel):
    user: UserOut
    permissions: list[str]


class AuthOut(BaseModel):
    """Login/refresh response.

    Browsers (default) receive tokens only as httpOnly cookies. Clients sending
    ``X-Auth-Transport: bearer`` receive them in the body instead.
    """

    user: UserOut
    access_expires_at: datetime
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: Literal["bearer"] = "bearer"  # noqa: S105


class RegisterOut(BaseModel):
    user: UserOut
    verification_required: bool


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    user_agent: str | None
    current: bool = False


class MessageOut(BaseModel):
    message: str


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        phone=user.phone,
        full_name=user.full_name,
        preferred_locale=user.preferred_locale,
        status=user.status,
        email_verified=user.email_verified,
        phone_verified_at=user.phone_verified_at,
        created_at=user.created_at,
        roles=sorted(user.roles),
    )
