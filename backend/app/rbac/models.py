from __future__ import annotations

from sqlalchemy import CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RoleRecord(Base):
    """Mirror of :class:`app.rbac.catalog.Role` for foreign keys and admin display."""

    __tablename__ = "roles"
    __table_args__ = (CheckConstraint("rank BETWEEN 0 AND 100", name="rank_range"),)

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name_ar: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
