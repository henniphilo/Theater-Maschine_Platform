"""create cues table

Revision ID: 20260723_0004
Revises: 20260723_0003
Create Date: 2026-07-23

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_0004"
down_revision: Union[str, None] = "20260723_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cues",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("production_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("cue_type", sa.String(length=32), nullable=False),
        sa.Column("asset_id", sa.String(length=36), nullable=True),
        sa.Column("device_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cooldown_seconds", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["production_id"], ["productions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cues_production_id"), "cues", ["production_id"], unique=False)
    op.create_index(op.f("ix_cues_cue_type"), "cues", ["cue_type"], unique=False)
    op.create_index(op.f("ix_cues_asset_id"), "cues", ["asset_id"], unique=False)
    op.create_index(op.f("ix_cues_device_id"), "cues", ["device_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_cues_device_id"), table_name="cues")
    op.drop_index(op.f("ix_cues_asset_id"), table_name="cues")
    op.drop_index(op.f("ix_cues_cue_type"), table_name="cues")
    op.drop_index(op.f("ix_cues_production_id"), table_name="cues")
    op.drop_table("cues")
