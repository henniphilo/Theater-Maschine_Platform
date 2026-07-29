"""create dramaturgy_decision_events table

Revision ID: 20260729_0007
Revises: 20260723_0006
Create Date: 2026-07-29

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0007"
down_revision: Union[str, None] = "20260723_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dramaturgy_decision_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("text_snippet", sa.Text(), nullable=False, server_default=""),
        sa.Column("cue_id", sa.String(length=120), nullable=True),
        sa.Column("decision_kind", sa.String(length=32), nullable=False, server_default="execute"),
        sa.Column("reason_short", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("dramaturgical_function", sa.String(length=32), nullable=False, server_default="support"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("decision_status", sa.String(length=32), nullable=False, server_default="scheduled"),
        sa.Column("executed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("blocked_reason", sa.String(length=120), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dramaturgy_decision_events_session_id",
        "dramaturgy_decision_events",
        ["session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_dramaturgy_decision_events_session_id", table_name="dramaturgy_decision_events")
    op.drop_table("dramaturgy_decision_events")
