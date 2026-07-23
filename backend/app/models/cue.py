"""Generic Cue model — executable action belonging to a production.

Assets are not executable; Cues are. Legacy VisualCue/SoundCue/LightCue remain
the adapter-layer shapes via ``cue_compat``.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CueType(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"
    LIGHT = "light"
    OSC = "osc"
    MIDI = "midi"
    TEXT = "text"
    WAIT = "wait"


CUE_TYPES = frozenset(t.value for t in CueType)


class Cue(Base):
    """Executable instruction scoped to a production."""

    __tablename__ = "cues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    production_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("productions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    cue_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    asset_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Device FK arrives with Alembic 20260723_0005; soft reference kept on the ORM
    # so create_all / older DBs remain usable before the migration runs.
    device_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cooldown_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
