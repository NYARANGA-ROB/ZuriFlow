"""add agent evaluation tables

Revision ID: v1w2x3y4z5a6
Revises: u0v1w2x3y4z5
Create Date: 2026-08-24 06:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v1w2x3y4z5a6"
down_revision: Union[str, None] = "u0v1w2x3y4z5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_eval_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=True),
        sa.Column("workflow_definition_id", sa.Integer(), nullable=True),
        sa.Column("baseline_definition_id", sa.Integer(), nullable=True),
        sa.Column("trigger", sa.String(), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(), nullable=False, server_default="completed"),
        sa.Column("scenario_filter", sa.String(), nullable=True),
        sa.Column("score_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "comparison_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")
        ),
        sa.Column(
            "metrics_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.ForeignKeyConstraint(["workflow_definition_id"], ["workflow_definitions.id"]),
        sa.ForeignKeyConstraint(["baseline_definition_id"], ["workflow_definitions.id"]),
    )
    op.create_index(
        "ix_agent_eval_runs_org_created",
        "agent_eval_runs",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_agent_eval_runs_org_workflow",
        "agent_eval_runs",
        ["organization_id", "workflow_id"],
    )

    op.create_table(
        "agent_eval_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("scenario_id", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "expected_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")
        ),
        sa.Column(
            "actual_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")
        ),
        sa.Column(
            "evaluation_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")
        ),
        sa.Column(
            "transcript_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")
        ),
        sa.Column(
            "tool_calls_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")
        ),
        sa.Column(
            "workflow_path_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_eval_runs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_agent_eval_results_run", "agent_eval_results", ["run_id"])
    op.create_index(
        "ix_agent_eval_results_org_scenario",
        "agent_eval_results",
        ["organization_id", "scenario_id"],
    )

    op.create_table(
        "agent_eval_production_samples",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=True),
        sa.Column("run_reference_hash", sa.String(), nullable=True),
        sa.Column("consent_ok", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "anonymized_turns",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column(
            "training_eligible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("governance_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
    )
    op.create_index(
        "ix_agent_eval_prod_org_created",
        "agent_eval_production_samples",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_eval_prod_org_created", table_name="agent_eval_production_samples")
    op.drop_table("agent_eval_production_samples")
    op.drop_index("ix_agent_eval_results_org_scenario", table_name="agent_eval_results")
    op.drop_index("ix_agent_eval_results_run", table_name="agent_eval_results")
    op.drop_table("agent_eval_results")
    op.drop_index("ix_agent_eval_runs_org_workflow", table_name="agent_eval_runs")
    op.drop_index("ix_agent_eval_runs_org_created", table_name="agent_eval_runs")
    op.drop_table("agent_eval_runs")
