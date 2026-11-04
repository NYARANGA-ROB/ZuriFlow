"""add conversation quality evaluation table

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-06-24 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, None] = "h8i9j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_quality_evaluations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("workflow_run_id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=True),
        sa.Column("model_version", sa.String(), server_default=sa.text("'cq-v1'"), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column(
            "dimension_scores",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column(
            "metrics",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column(
            "regression",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column(
            "flags",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"]),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_run_id", name="uq_cq_evaluations_workflow_run"),
    )
    op.create_index(
        "ix_cq_evaluations_org_evaluated",
        "conversation_quality_evaluations",
        ["organization_id", "evaluated_at"],
        unique=False,
    )
    op.create_index(
        "ix_cq_evaluations_org_workflow",
        "conversation_quality_evaluations",
        ["organization_id", "workflow_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_cq_evaluations_org_workflow", table_name="conversation_quality_evaluations")
    op.drop_index("ix_cq_evaluations_org_evaluated", table_name="conversation_quality_evaluations")
    op.drop_table("conversation_quality_evaluations")
