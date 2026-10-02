"""Location hierarchy: governorate → city → district → neighborhood.

Nothing is Basra-specific: every level is data. Boundaries and centroids are
optional PostGIS geometries (WGS84 / EPSG:4326) so a city can be added before
its polygon is available; spatial features then degrade gracefully.
"""

from __future__ import annotations

import uuid
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

SRID = 4326


def point() -> Geometry:
    return Geometry(geometry_type="POINT", srid=SRID, spatial_index=False)


def area() -> Geometry:
    return Geometry(geometry_type="MULTIPOLYGON", srid=SRID, spatial_index=False)


class _Place(UUIDPrimaryKeyMixin, TimestampMixin):
    name_ar: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    centroid: Mapped[Any | None] = mapped_column(point())
    boundary: Mapped[Any | None] = mapped_column(area())
    # Where the geometry came from (e.g. "OpenStreetMap contributors (ODbL)" or
    # "DEMO approximate — not authoritative"). Shown wherever it is displayed.
    geometry_source: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Governorate(_Place, Base):
    __tablename__ = "governorates"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_governorates_slug"),
        Index("ix_governorates_boundary", "boundary", postgresql_using="gist"),
    )

    code: Mapped[str] = mapped_column(String(8), nullable=False, unique=True)


class City(_Place, Base):
    __tablename__ = "cities"
    __table_args__ = (
        UniqueConstraint("governorate_id", "slug", name="uq_cities_governorate_slug"),
        Index("ix_cities_boundary", "boundary", postgresql_using="gist"),
    )

    governorate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("governorates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


class District(_Place, Base):
    __tablename__ = "districts"
    __table_args__ = (
        UniqueConstraint("city_id", "slug", name="uq_districts_city_slug"),
        Index("ix_districts_boundary", "boundary", postgresql_using="gist"),
    )

    city_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cities.id", ondelete="RESTRICT"), nullable=False, index=True
    )


class Neighborhood(_Place, Base):
    __tablename__ = "neighborhoods"
    __table_args__ = (
        UniqueConstraint("district_id", "slug", name="uq_neighborhoods_district_slug"),
        Index("ix_neighborhoods_boundary", "boundary", postgresql_using="gist"),
    )

    district_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("districts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
