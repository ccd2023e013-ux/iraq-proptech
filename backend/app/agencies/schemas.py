from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator

from app.users.validation import normalize_iraqi_phone


def _phone(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return normalize_iraqi_phone(value)


class AgencyIn(BaseModel):
    name_ar: str = Field(min_length=2, max_length=150)
    name_en: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, max_length=4000)
    phone: str | None = Field(default=None, max_length=30)
    whatsapp: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    website: HttpUrl | None = None
    license_number: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=300)
    city_id: uuid.UUID | None = None

    _p = field_validator("phone", "whatsapp")(_phone)

    @field_validator("website")
    @classmethod
    def _https_only(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None and value.scheme != "https":
            raise ValueError("Website must use https")
        return value


class AgencyUpdate(AgencyIn):
    name_ar: str | None = Field(default=None, min_length=2, max_length=150)  # type: ignore[assignment]


class AgencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name_ar: str
    name_en: str | None
    slug: str
    description: str | None
    phone: str | None
    whatsapp: str | None
    email: str | None
    website: str | None
    license_number: str | None
    address: str | None
    city_id: uuid.UUID | None
    status: str
    verified_at: datetime | None
    is_demo: bool
    created_at: datetime


class AgencyDecisionIn(BaseModel):
    decision: Literal["VERIFY", "REJECT", "SUSPEND"]
    reason: str | None = Field(default=None, max_length=1000)


class InvitationIn(BaseModel):
    email: EmailStr


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_id: uuid.UUID
    email: str
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None
    agency_name: str | None = None


class MemberOut(BaseModel):
    user_id: uuid.UUID
    full_name: str
    role: str
    title: str | None
    joined_at: datetime


class AgentProfileIn(BaseModel):
    display_name: str = Field(min_length=2, max_length=150)
    bio: str | None = Field(default=None, max_length=4000)
    license_number: str | None = Field(default=None, max_length=100)
    public_phone: str | None = Field(default=None, max_length=30)
    whatsapp: str | None = Field(default=None, max_length=30)
    years_experience: int | None = Field(default=None, ge=0, le=80)
    languages: str | None = Field(default=None, max_length=100)

    _p = field_validator("public_phone", "whatsapp")(_phone)


class AgentProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    display_name: str
    bio: str | None
    license_number: str | None
    public_phone: str | None
    whatsapp: str | None
    years_experience: int | None
    languages: str | None
    verified_at: datetime | None
    agency_id: uuid.UUID | None = None
    agency_name: str | None = None
