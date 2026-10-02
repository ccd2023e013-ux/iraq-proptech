from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.crm.models import (
    ActivityKind,
    AppointmentStatus,
    ContactPreference,
    LeadSource,
    Priority,
)
from app.users.validation import normalize_iraqi_phone

Currency = Literal["IQD", "USD"]


def _phone(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return normalize_iraqi_phone(value)


# --------------------------------------------------------------------------- inquiries


class InquiryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    message: str = Field(min_length=5, max_length=3000)
    preferred_contact: ContactPreference = ContactPreference.ANY

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str | None) -> str | None:
        return _phone(value)

    @model_validator(mode="after")
    def _reachable(self) -> InquiryCreate:
        if not self.phone and not self.email:
            raise ValueError("Provide a phone number or an email address")
        return self


class InquiryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    property_id: uuid.UUID
    name: str
    message: str
    preferred_contact: str
    created_at: datetime


class MyInquiryOut(InquiryOut):
    property_title_ar: str | None = None
    property_title_en: str | None = None
    property_reference: str | None = None


# --------------------------------------------------------------------------- statuses


class LeadStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name_ar: str
    name_en: str
    sort_order: int
    is_terminal: bool
    is_won: bool
    is_active: bool
    is_system: bool


class LeadStatusUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_ar: str = Field(min_length=1, max_length=80)
    name_en: str = Field(min_length=1, max_length=80)
    sort_order: int = Field(ge=0, le=1000)
    is_active: bool = True
    # Only used when creating a custom stage; core stages keep their semantics.
    is_terminal: bool = False
    is_won: bool = False


# --------------------------------------------------------------------------- customers & leads


class CustomerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str | None) -> str | None:
        return _phone(value)


class CustomerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str | None) -> str | None:
        return _phone(value)


class CustomerOut(BaseModel):
    id: uuid.UUID
    full_name: str
    phone: str | None
    email: str | None
    notes: str | None
    source: str
    is_platform_user: bool
    agency_id: uuid.UUID | None
    created_at: datetime
    lead_count: int = 0


class PersonRef(BaseModel):
    id: uuid.UUID
    full_name: str


class PropertyRef(BaseModel):
    id: uuid.UUID
    reference_code: str
    title_ar: str
    title_en: str | None
    status: str


class LeadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: uuid.UUID | None = None
    customer: CustomerIn | None = None
    property_id: uuid.UUID | None = None
    source: LeadSource = LeadSource.MANUAL
    priority: Priority = Priority.NORMAL
    budget_min: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    budget_max: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    budget_currency: Currency | None = None
    next_follow_up_at: datetime | None = None
    note: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def _check(self) -> LeadCreate:
        if (self.customer_id is None) == (self.customer is None):
            raise ValueError("Provide exactly one of customer_id or customer")
        if self.source == LeadSource.INQUIRY:
            raise ValueError("INQUIRY leads are created from inquiries")
        check_budget(self.budget_min, self.budget_max, self.budget_currency)
        return self


def check_budget(lo: Decimal | None, hi: Decimal | None, currency: str | None) -> None:
    if (lo is not None or hi is not None) and currency is None:
        raise ValueError("A budget needs a currency (IQD or USD); amounts are never converted")
    if lo is not None and hi is not None and lo > hi:
        raise ValueError("budget_min must not exceed budget_max")


class LeadUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status_code: str | None = Field(default=None, max_length=24)
    lost_reason: str | None = Field(default=None, max_length=2000)
    priority: Priority | None = None
    assigned_to_id: uuid.UUID | None = None
    budget_min: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    budget_max: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    budget_currency: Currency | None = None
    next_follow_up_at: datetime | None = None


class LeadOut(BaseModel):
    id: uuid.UUID
    status_code: str
    source: str
    priority: str
    customer: CustomerOut
    property: PropertyRef | None
    agency_id: uuid.UUID | None
    owner: PersonRef | None
    assigned_to: PersonRef | None
    budget_min: Decimal | None
    budget_max: Decimal | None
    budget_currency: str | None
    next_follow_up_at: datetime | None
    last_activity_at: datetime | None
    closed_at: datetime | None
    lost_reason: str | None
    created_at: datetime
    updated_at: datetime
    can_manage: bool
    can_assign: bool


class ActivityIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ActivityKind
    body: str = Field(min_length=1, max_length=5000)
    occurred_at: datetime | None = None


class ActivityOut(BaseModel):
    id: uuid.UUID
    kind: str
    body: str | None
    data: dict[str, Any] | None
    actor: PersonRef | None
    occurred_at: datetime


# --------------------------------------------------------------------------- tasks & appointments


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    lead_id: uuid.UUID | None = None
    assigned_to_id: uuid.UUID | None = None
    due_at: datetime | None = None
    priority: Priority = Priority.NORMAL


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    assigned_to_id: uuid.UUID | None = None
    due_at: datetime | None = None
    priority: Priority | None = None
    completed: bool | None = None


class TaskOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    lead_id: uuid.UUID | None
    assigned_to: PersonRef | None
    due_at: datetime | None
    completed_at: datetime | None
    priority: str
    overdue: bool
    created_at: datetime


class AppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starts_at: datetime
    ends_at: datetime | None = None
    property_id: uuid.UUID | None = None
    location_text: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def _order(self) -> AppointmentCreate:
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class AppointmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: AppointmentStatus | None = None
    location_text: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=5000)


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lead_id: uuid.UUID
    property_id: uuid.UUID | None
    starts_at: datetime
    ends_at: datetime | None
    location_text: str | None
    status: str
    notes: str | None


# --------------------------------------------------------------------------- dashboard


class StatusCount(BaseModel):
    code: str
    count: int


class CrmDashboard(BaseModel):
    total_open: int
    new_last_7_days: int
    by_status: list[StatusCount]
    overdue_follow_ups: int
    tasks_due_today: int
    tasks_overdue: int
    upcoming_appointments: list[AppointmentOut]
    won: int
    lost: int
    conversion_rate: float | None = Field(
        description="won / (won + lost); null without closed leads"
    )


# --------------------------------------------------------------------------- conversations


class MessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=4000)


class MessageOut(BaseModel):
    id: uuid.UUID
    sender: PersonRef | None
    body: str
    created_at: datetime
    read_at: datetime | None
    mine: bool


class ConversationOut(BaseModel):
    id: uuid.UUID
    property: PropertyRef | None
    lead_id: uuid.UUID | None
    customer: PersonRef | None
    lister: PersonRef | None
    last_message_at: datetime | None
    last_message: str | None
    unread: int
    role: Literal["customer", "lister"]
