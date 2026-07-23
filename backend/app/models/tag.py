"""Tag model — production-scoped labels linked to Assets (many-to-many)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.asset import Asset

asset_tags = Table(
    "asset_tags",
    Base.metadata,
    Column(
        "asset_id",
        String(36),
        ForeignKey("assets.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        String(36),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Tag(Base):
    """Named label belonging to a production; no AI classification."""

    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("production_id", "name", name="uq_tags_production_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    production_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("productions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    assets: Mapped[list[Asset]] = relationship(
        "Asset",
        secondary=asset_tags,
        back_populates="tags",
    )
