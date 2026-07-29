"""Persisted dramaturgy decision events for post-show analysis."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DramaturgyDecisionEventRow(Base):
    __tablename__ = "dramaturgy_decision_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    text_snippet: Mapped[str] = mapped_column(Text, default="")
    cue_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decision_kind: Mapped[str] = mapped_column(String(32), default="execute")
    reason_short: Mapped[str] = mapped_column(String(160), default="")
    dramaturgical_function: Mapped[str] = mapped_column(String(32), default="support")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    decision_status: Mapped[str] = mapped_column(String(32), default="scheduled")
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
