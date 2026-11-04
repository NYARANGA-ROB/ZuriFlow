"""add durable orchestration tables

Revision ID: l1m2n3o4p5q6
Revises: k0l1m2n3o4p5
Create Date: 2026-06-24 21:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l1m2n3o4p5q6"
down_revision: Union[str, None] = "k0l1m2n3o4p5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "durable_orchestrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("workflow_run_id", sa.Integer(), nullable=True),
        sa.Column("orchestration_key", sa.String(), nullable=False),
        sa.Column("definition_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("current_step", sa.String(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "state",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column(
            "saga_stack",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("next_wake_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "orchestration_key",
            name="uq_durable_orchestrations_org_key",
        ),
    )
    op.create_index(
        "ix_durable_orchestrations_org_status",
        "durable_orchestrations",
        ["organization_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_durable_orchestrations_wake",
        "durable_orchestrations",
        ["status", "next_wake_at"],
        unique=False,
    )

    op.create_table(
        "durable_orchestration_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orchestration_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column(
            "payload",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["orchestration_id"], ["durable_orchestrations.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_durable_orch_events_orch_created",
        "durable_orchestration_events",
        ["orchestration_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "durable_scheduled_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orchestration_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(), nullable=False),
        sa.Column(
            "payload",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("5"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["orchestration_id"], ["durable_orchestrations.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_durable_scheduled_tasks_due",
        "durable_scheduled_tasks",
        ["status", "run_at"],
        unique=False,
    )
    op.create_index(
        "ix_durable_scheduled_tasks_orch",
        "durable_scheduled_tasks",
        ["orchestration_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_durable_scheduled_tasks_orch", table_name="durable_scheduled_tasks")
    op.drop_index("ix_durable_scheduled_tasks_due", table_name="durable_scheduled_tasks")
    op.drop_table("durable_scheduled_tasks")
    op.drop_index(
        "ix_durable_orch_events_orch_created",
        table_name="durable_orchestration_events",
    )
    op.drop_table("durable_orchestration_events")
    op.drop_index("ix_durable_orchestrations_wake", table_name="durable_orchestrations")
    op.drop_index("ix_durable_orchestrations_org_status", table_name="durable_orchestrations")
    op.drop_table("durable_orchestrations")
