from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.geo.models import point
from app.properties.enums import (
    Condition,
    Currency,
    DocumentType,
    Furnishing,
    LocationPrivacy,
    MediaKind,
    ModerationState,
    OwnershipDocument,
    PropertyStatus,
    Purpose,
    RentPeriod,
    VerificationKind,
    VerificationResult,
    sql_in,
)

# Normalized text used by keyword search (see migration 0004 for normalize_ar).
SEARCH_TEXT_SQL = (
    "normalize_ar(coalesce(title_ar, '') || ' ' || coalesce(title_en, '') || ' ' || "
    "coalesce(description_ar, '') || ' ' || coalesce(description_en, '') || ' ' || "
    "coalesce(street, '') || ' ' || coalesce(address_text, '') || ' ' || reference_code)"
)


class PropertyType(Base):
    __tablename__ = "property_types"
    __table_args__ = (
        CheckConstraint(
            "category IN ('RESIDENTIAL','COMMERCIAL','LAND','AGRICULTURAL','INDUSTRIAL','OTHER')",
            name="category_valid",
        ),
    )

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(80), nullable=False)
    name_en: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Amenity(Base):
    __tablename__ = "amenities"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(80), nullable=False)
    name_en: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PropertyAmenity(Base):
    __tablename__ = "property_amenities"

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), primary_key=True
    )
    amenity_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("amenities.code", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )


class Property(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A listing: one property offered for one purpose by one lister.

    Facts here are exactly what the lister declared (never invented or
    silently modified). Price is stored in its original currency only.
    """

    __tablename__ = "properties"
    __table_args__ = (
        CheckConstraint(f"purpose IN ({sql_in(Purpose)})", name="purpose_valid"),
        CheckConstraint(f"status IN ({sql_in(PropertyStatus)})", name="status_valid"),
        CheckConstraint(f"currency IN ({sql_in(Currency)})", name="currency_valid"),
        CheckConstraint(
            f"rent_period IS NULL OR rent_period IN ({sql_in(RentPeriod)})",
            name="rent_period_valid",
        ),
        CheckConstraint(
            f"condition IS NULL OR condition IN ({sql_in(Condition)})", name="condition_valid"
        ),
        CheckConstraint(
            f"furnishing IS NULL OR furnishing IN ({sql_in(Furnishing)})", name="furnishing_valid"
        ),
        CheckConstraint(
            f"ownership_document IN ({sql_in(OwnershipDocument)})", name="ownership_valid"
        ),
        CheckConstraint(
            f"location_privacy IN ({sql_in(LocationPrivacy)})", name="location_privacy_valid"
        ),
        CheckConstraint(
            "(price_on_request AND price_amount IS NULL) OR "
            "(NOT price_on_request AND price_amount IS NOT NULL AND price_amount > 0)",
            name="price_present",
        ),
        CheckConstraint(
            "purpose NOT IN ('RENT','LEASE') OR rent_period IS NOT NULL", name="rent_needs_period"
        ),
        CheckConstraint("area_m2 IS NULL OR area_m2 > 0", name="area_positive"),
        CheckConstraint("land_area_m2 IS NULL OR land_area_m2 > 0", name="land_area_positive"),
        CheckConstraint("bedrooms IS NULL OR bedrooms BETWEEN 0 AND 100", name="bedrooms_range"),
        CheckConstraint("bathrooms IS NULL OR bathrooms BETWEEN 0 AND 100", name="bathrooms_range"),
        CheckConstraint("floors IS NULL OR floors BETWEEN 0 AND 200", name="floors_range"),
        CheckConstraint(
            "floor_number IS NULL OR floor_number BETWEEN -5 AND 200", name="floor_number_range"
        ),
        CheckConstraint(
            "year_built IS NULL OR year_built BETWEEN 1800 AND 2100", name="year_built_range"
        ),
        Index("ix_properties_location", "location", postgresql_using="gist"),
        Index("ix_properties_display_location", "display_location", postgresql_using="gist"),
        Index("ix_properties_status_published", "status", "published_at"),
        Index("ix_properties_city_purpose_type", "city_id", "purpose", "property_type_code"),
        Index("ix_properties_search_vector", "search_vector", postgresql_using="gin"),
        Index(
            "ix_properties_search_text_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
        Index("ix_properties_status_price", "status", "currency", "price_amount"),
        Index("ix_properties_status_area", "status", "area_m2"),
    )

    reference_code: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)

    title_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    title_en: Mapped[str | None] = mapped_column(String(200))
    description_ar: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)

    property_type_code: Mapped[str] = mapped_column(
        String(32), ForeignKey("property_types.code", ondelete="RESTRICT"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    rent_period: Mapped[str | None] = mapped_column(String(10))

    # Money: original amount + currency, never converted in storage.
    price_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="IQD")
    price_on_request: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    negotiable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    area_m2: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    land_area_m2: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    bedrooms: Mapped[int | None] = mapped_column(SmallInteger)
    bathrooms: Mapped[int | None] = mapped_column(SmallInteger)
    floors: Mapped[int | None] = mapped_column(SmallInteger)
    floor_number: Mapped[int | None] = mapped_column(SmallInteger)
    year_built: Mapped[int | None] = mapped_column(SmallInteger)
    condition: Mapped[str | None] = mapped_column(String(24))
    furnishing: Mapped[str | None] = mapped_column(String(16))
    ownership_document: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")

    # Location
    governorate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("governorates.id", ondelete="RESTRICT"), nullable=False
    )
    city_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cities.id", ondelete="RESTRICT"), nullable=False
    )
    district_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("districts.id", ondelete="SET NULL"), index=True
    )
    neighborhood_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("neighborhoods.id", ondelete="SET NULL"), index=True
    )
    street: Mapped[str | None] = mapped_column(String(200))
    address_text: Mapped[str | None] = mapped_column(String(300))
    # Exact point: private (owner, agents, moderators).
    location: Mapped[Any | None] = mapped_column(point())
    # What the public sees, derived from location + privacy (NULL when hidden).
    display_location: Mapped[Any | None] = mapped_column(point())
    location_privacy: Mapped[str] = mapped_column(String(12), nullable=False, default="APPROXIMATE")

    # Lifecycle
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    status_reason: Mapped[str | None] = mapped_column(Text)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Who manages the listing
    lister_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    agency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="SET NULL"), index=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    # Contact preferences (consent to show lister contact on the listing)
    show_phone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_whatsapp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    virtual_tour_url: Mapped[str | None] = mapped_column(String(500))

    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Generated by PostgreSQL (never written by the application).
    search_text: Mapped[str | None] = mapped_column(
        Text, Computed(SEARCH_TEXT_SQL, persisted=True), deferred=True
    )
    search_vector: Mapped[Any | None] = mapped_column(
        TSVECTOR,
        Computed(f"to_tsvector('simple', {SEARCH_TEXT_SQL})", persisted=True),
        deferred=True,
    )

    amenity_links: Mapped[list[PropertyAmenity]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )
    media: Mapped[list[PropertyMedia]] = relationship(
        lazy="selectin",
        order_by="PropertyMedia.sort_order",
        primaryjoin="and_(Property.id == PropertyMedia.property_id, "
        "PropertyMedia.deleted_at.is_(None))",
        viewonly=True,
    )

    @property
    def amenity_codes(self) -> list[str]:
        return sorted(link.amenity_code for link in self.amenity_links)

    @property
    def is_public(self) -> bool:
        return self.status == PropertyStatus.APPROVED and self.deleted_at is None


class PropertyMedia(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "property_media"
    __table_args__ = (
        CheckConstraint(f"kind IN ({sql_in(MediaKind)})", name="kind_valid"),
        CheckConstraint(f"moderation IN ({sql_in(ModerationState)})", name="moderation_valid"),
        Index("ix_property_media_property_order", "property_id", "sort_order"),
        Index("ix_property_media_sha256", "sha256"),
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False)
    thumbnail_key: Mapped[str | None] = mapped_column(String(300))
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    caption: Mapped[str | None] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # 64-bit difference hash for near-duplicate image detection.
    perceptual_hash: Mapped[int | None] = mapped_column(BigInteger)
    moderation: Mapped[str] = mapped_column(String(10), nullable=False, default="APPROVED")
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PropertyDocument(UUIDPrimaryKeyMixin, Base):
    """Private supporting documents (title deeds, IDs...). Never public."""

    __tablename__ = "property_documents"
    __table_args__ = (
        CheckConstraint(f"doc_type IN ({sql_in(DocumentType)})", name="doc_type_valid"),
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doc_type: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PropertyPriceHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "property_price_history"
    __table_args__ = (Index("ix_property_price_history_property", "property_id", "changed_at"),)

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False
    )
    price_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    price_on_request: Mapped[bool] = mapped_column(Boolean, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class PropertyStatusHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "property_status_history"
    __table_args__ = (Index("ix_property_status_history_property", "property_id", "changed_at"),)

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class PropertyVerification(UUIDPrimaryKeyMixin, Base):
    """Evidence-based verification records (who checked what, when, with what result)."""

    __tablename__ = "property_verifications"
    __table_args__ = (
        CheckConstraint(f"kind IN ({sql_in(VerificationKind)})", name="kind_valid"),
        CheckConstraint(f"result IN ({sql_in(VerificationResult)})", name="result_valid"),
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    result: Mapped[str] = mapped_column(String(8), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("property_documents.id", ondelete="SET NULL")
    )
    verified_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
