"""Property Media Studio: render jobs (storyboard → video) with pluggable renderers."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Renderer(StrEnum):
    BROWSER = "BROWSER"  # rendered on the user's device (free; default)
    SERVER = "SERVER"  # server-side ffmpeg worker (not enabled on the free tier)
    EXTERNAL = "EXTERNAL"  # third-party video/voice provider (needs keys)


class JobStatus(StrEnum):
    STORYBOARD_READY = "STORYBOARD_READY"
    RENDERING = "RENDERING"
    DONE = "DONE"
    FAILED = "FAILED"


class MediaJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "media_jobs"
    __table_args__ = (
        CheckConstraint("renderer IN ('BROWSER','SERVER','EXTERNAL')", name="renderer_valid"),
        CheckConstraint(
            "status IN ('STORYBOARD_READY','RENDERING','DONE','FAILED')", name="status_valid"
        ),
        CheckConstraint("format IN ('landscape','vertical')", name="format_valid"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    renderer: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    storyboard: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output_key: Mapped[str | None] = mapped_column(String(255))
    output_type: Mapped[str | None] = mapped_column(String(40))
    output_bytes: Mapped[int | None] = mapped_column(BigInteger)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(String(300))
