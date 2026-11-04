"""add platform events table

Revision ID: m2n3o4p5q6r7
Revises: l1m2n3o4p5q6
Create Date: 2026-06-24 22:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m2n3o4p5q6r7"
down_revision: Union[str, None] = "l1m2n3o4p5q6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("source", sa.String(), server_default=sa.text("''"), nullable=False),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column(
            "payload",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_platform_events_org_created",
        "platform_events",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_platform_events_org_type",
        "platform_events",
        ["organization_id", "event_type"],
        unique=False,
    )
    op.create_index(
        "ix_platform_events_correlation",
        "platform_events",
        ["correlation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_platform_events_correlation", table_name="platform_events")
    op.drop_index("ix_platform_events_org_type", table_name="platform_events")
    op.drop_index("ix_platform_events_org_created", table_name="platform_events")
    op.drop_table("platform_events")
