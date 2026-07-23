"""Device model — configured technical output / connection.

Hardware communication lives in OutputAdapters; Devices only store identity,
adapter type, and (optionally encrypted) connection configuration.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AdapterType(StrEnum):
    DRY_RUN = "dry_run"
    OSC = "osc"
    MIDI = "midi"
    PIXERA = "pixera"
    EOS_TCP = "eos_tcp"


ADAPTER_TYPES = frozenset(t.value for t in AdapterType)
DEFAULT_ADAPTER_TYPE = AdapterType.DRY_RUN.value


class Device(Base):
    """Configured output device belonging optionally to a production."""

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    production_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("productions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    adapter_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DEFAULT_ADAPTER_TYPE,
        index=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Sensitive connection params — never expose raw values via API reads.
    # May hold plaintext JSON or an encryption envelope (see device_secrets).
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # Opaque sealed blob when encryption is active; JSON column stays empty/redacted meta.
    configuration_sealed: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
