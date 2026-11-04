"""add customer timeline entries

Revision ID: n3o4p5q6r7s8
Revises: m2n3o4p5q6r7
Create Date: 2026-06-24 22:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n3o4p5q6r7s8"
down_revision: Union[str, None] = "m2n3o4p5q6r7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_timeline_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("phone_e164", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "payload",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("workflow_run_id", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("transaction_id", sa.Integer(), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("journey_state", sa.String(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("platform_event_id", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["whatsapp_conversations.id"]),
        sa.ForeignKeyConstraint(["transaction_id"], ["mpesa_transactions.id"]),
        sa.ForeignKeyConstraint(["platform_event_id"], ["platform_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_customer_timeline_org_phone_occurred",
        "customer_timeline_entries",
        ["organization_id", "phone_e164", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_customer_timeline_org_customer_occurred",
        "customer_timeline_entries",
        ["organization_id", "customer_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_customer_timeline_org_customer_occurred",
        table_name="customer_timeline_entries",
    )
    op.drop_index(
        "ix_customer_timeline_org_phone_occurred",
        table_name="customer_timeline_entries",
    )
    op.drop_table("customer_timeline_entries")
