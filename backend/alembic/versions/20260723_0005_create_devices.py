"""create devices table

Revision ID: 20260723_0005
Revises: 20260723_0004
Create Date: 2026-07-23

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_0005"
down_revision: Union[str, None] = "20260723_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("production_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "adapter_type",
            sa.String(length=32),
            nullable=False,
            server_default="dry_run",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("configuration_sealed", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_devices_production_id"), "devices", ["production_id"], unique=False)
    op.create_index(op.f("ix_devices_adapter_type"), "devices", ["adapter_type"], unique=False)

    # Soft cue.device_id → devices.id (SET NULL on delete); keep cues.device_id nullable.
    op.create_foreign_key(
        "fk_cues_device_id_devices",
        "cues",
        "devices",
        ["device_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_cues_device_id_devices", "cues", type_="foreignkey")
    op.drop_index(op.f("ix_devices_adapter_type"), table_name="devices")
    op.drop_index(op.f("ix_devices_production_id"), table_name="devices")
    op.drop_table("devices")
