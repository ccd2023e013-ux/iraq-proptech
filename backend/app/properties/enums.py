"""Enumerations of the property domain (values are stable API/DB codes)."""

from __future__ import annotations

from enum import StrEnum


class Purpose(StrEnum):
    SALE = "SALE"  # بيع
    RENT = "RENT"  # إيجار
    LEASE = "LEASE"  # تأجير طويل الأمد / تجاري
    RAHN = "RAHN"  # رهن: lump-sum deposit instead of monthly rent (common in Iraq)
    MUSATAHA = "MUSATAHA"  # مساطحة: long-term land lease with the right to build
    EXCHANGE = "EXCHANGE"  # مبادلة / مراوس


class RentPeriod(StrEnum):
    DAILY = "DAILY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class Currency(StrEnum):
    IQD = "IQD"
    USD = "USD"


class PropertyStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"  # live / published
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"  # taken down by moderation
    ARCHIVED = "ARCHIVED"
    SOLD = "SOLD"
    RENTED = "RENTED"
    EXPIRED = "EXPIRED"


class Condition(StrEnum):
    NEW = "NEW"
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    NEEDS_RENOVATION = "NEEDS_RENOVATION"
    UNDER_CONSTRUCTION = "UNDER_CONSTRUCTION"


class Furnishing(StrEnum):
    UNFURNISHED = "UNFURNISHED"
    SEMI_FURNISHED = "SEMI_FURNISHED"
    FURNISHED = "FURNISHED"


class OwnershipDocument(StrEnum):
    """Title type *declared by the lister* — never shown as verified unless checked."""

    TAPU = "TAPU"  # طابو صرف (freehold title deed)
    AGRICULTURAL = "AGRICULTURAL"  # زراعي
    HUJJA = "HUJJA"  # حجة (informal deed)
    INVESTMENT = "INVESTMENT"  # سند استثمار
    MUSATAHA = "MUSATAHA"  # عقد مساطحة
    SHARED = "SHARED"  # مشاع
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class LocationPrivacy(StrEnum):
    EXACT = "EXACT"  # exact point is public
    APPROXIMATE = "APPROXIMATE"  # public point is coarsened (~500 m) or the neighbourhood centre
    HIDDEN = "HIDDEN"  # no public point; area names only


class MediaKind(StrEnum):
    IMAGE = "IMAGE"
    FLOOR_PLAN = "FLOOR_PLAN"
    VIDEO = "VIDEO"


class ModerationState(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class DocumentType(StrEnum):
    TITLE_DEED = "TITLE_DEED"
    ID_DOCUMENT = "ID_DOCUMENT"
    POWER_OF_ATTORNEY = "POWER_OF_ATTORNEY"
    CONTRACT = "CONTRACT"
    PERMIT = "PERMIT"
    OTHER = "OTHER"


class VerificationKind(StrEnum):
    IDENTITY = "IDENTITY"
    DOCUMENT = "DOCUMENT"
    OWNERSHIP = "OWNERSHIP"
    LOCATION = "LOCATION"
    PHONE = "PHONE"
    AGENCY = "AGENCY"
    SITE_VISIT = "SITE_VISIT"


class VerificationResult(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"


def sql_in(enum: type[StrEnum]) -> str:
    """``'A','B'`` for CHECK constraints."""
    return ",".join(f"'{member.value}'" for member in enum)
