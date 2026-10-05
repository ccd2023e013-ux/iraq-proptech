"""Development Intelligence ("Future Iraq"): projects with mandatory provenance.

A project row is only a claim; its evidence rows say who published what, when,
and where to read it. Nothing is shown publicly without at least one evidence
row, and every field that could be mistaken for a plan (timeline, location)
carries its own precision/wording as published — never inferred.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.geo.models import point


class SourceKind(StrEnum):
    OFFICIAL = "OFFICIAL"  # government ministry, authority or state company
    PUBLIC = "PUBLIC"  # international organisation, open data
    MEDIA = "MEDIA"  # press report (lower confidence)
    DEMO = "DEMO"


class ProjectCategory(StrEnum):
    PORT = "PORT"
    ROAD = "ROAD"
    BRIDGE_TUNNEL = "BRIDGE_TUNNEL"
    RAIL = "RAIL"
    AIRPORT = "AIRPORT"
    WATER = "WATER"
    POWER = "POWER"
    HOUSING = "HOUSING"
    INDUSTRIAL = "INDUSTRIAL"
    COMMERCIAL = "COMMERCIAL"
    PUBLIC_FACILITY = "PUBLIC_FACILITY"
    INVESTMENT_OPPORTUNITY = "INVESTMENT_OPPORTUNITY"


class ProjectStatus(StrEnum):
    OPPORTUNITY = "OPPORTUNITY"  # offered to investors
    PLANNED = "PLANNED"
    TENDERED = "TENDERED"
    UNDER_CONSTRUCTION = "UNDER_CONSTRUCTION"
    TRIAL_OPERATION = "TRIAL_OPERATION"
    COMPLETED = "COMPLETED"
    ON_HOLD = "ON_HOLD"
    UNKNOWN = "UNKNOWN"


class LocationPrecision(StrEnum):
    EXACT = "EXACT"
    APPROXIMATE = "APPROXIMATE"  # placed at the published site/area, not surveyed
    AREA = "AREA"  # only the district/city is known


class Confidence(StrEnum):
    HIGH = "HIGH"  # official source, recent
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EvidenceSupports(StrEnum):
    EXISTENCE = "EXISTENCE"
    STATUS = "STATUS"
    TIMELINE = "TIMELINE"
    LOCATION = "LOCATION"
    FIGURES = "FIGURES"


def _in(values: type[StrEnum]) -> str:
    return ",".join(f"'{v.value}'" for v in values)


class DevelopmentSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "development_sources"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_in(SourceKind)})", name="kind_valid"),
        UniqueConstraint("url"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    organization: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    terms_note: Mapped[str | None] = mapped_column(String(500))


class DevelopmentProject(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "development_projects"
    __table_args__ = (
        CheckConstraint(f"category IN ({_in(ProjectCategory)})", name="category_valid"),
        CheckConstraint(f"status IN ({_in(ProjectStatus)})", name="status_valid"),
        CheckConstraint(
            f"location_precision IN ({_in(LocationPrecision)})", name="precision_valid"
        ),
        CheckConstraint(f"confidence IN ({_in(Confidence)})", name="confidence_valid"),
        UniqueConstraint("slug"),
        Index("ix_development_projects_location", "location", postgresql_using="gist"),
    )

    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(300), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    summary_ar: Mapped[str] = mapped_column(Text, nullable=False)
    summary_en: Mapped[str | None] = mapped_column(Text)
    location: Mapped[Any] = mapped_column(point(), nullable=False)
    location_precision: Mapped[str] = mapped_column(String(16), nullable=False)
    location_note: Mapped[str | None] = mapped_column(String(300))
    governorate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("governorates.id", ondelete="SET NULL"), index=True
    )
    # Only what the source states, in its own terms (e.g. "full operations in 2026").
    timeline_ar: Mapped[str | None] = mapped_column(String(300))
    timeline_en: Mapped[str | None] = mapped_column(String(300))
    target_year: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[str] = mapped_column(String(8), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    evidence: Mapped[list[DevelopmentEvidence]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )


class DevelopmentEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "development_evidence"
    __table_args__ = (
        CheckConstraint(f"supports IN ({_in(EvidenceSupports)})", name="supports_valid"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("development_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("development_sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    published_on: Mapped[date | None] = mapped_column(Date)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    excerpt: Mapped[str | None] = mapped_column(String(600))
    supports: Mapped[str] = mapped_column(String(16), nullable=False)

    project: Mapped[DevelopmentProject] = relationship(back_populates="evidence")
    source: Mapped[DevelopmentSource] = relationship(lazy="joined")
