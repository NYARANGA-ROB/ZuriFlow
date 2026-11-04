"""add kenyan continuous learning tables

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-06-24 16:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j0k1l2m3n4o5"
down_revision: Union[str, None] = "i9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kenyan_learning_samples",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("target", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("run_reference_hash", sa.String(), nullable=True),
        sa.Column("locale", sa.String(), server_default=sa.text("'mixed'"), nullable=False),
        sa.Column(
            "payload",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_kenyan_learning_samples_org_target",
        "kenyan_learning_samples",
        ["organization_id", "target"],
        unique=False,
    )
    op.create_index(
        "ix_kenyan_learning_samples_created",
        "kenyan_learning_samples",
        ["organization_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "kenyan_learning_label_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("sample_id", sa.Integer(), nullable=False),
        sa.Column("target", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("assigned_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "label_payload",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["sample_id"], ["kenyan_learning_samples.id"]),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_kenyan_learning_labels_org_status",
        "kenyan_learning_label_tasks",
        ["organization_id", "status"],
        unique=False,
    )

    op.create_table(
        "kenyan_learning_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("feedback_type", sa.String(), nullable=False),
        sa.Column(
            "payload",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("sample_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["sample_id"], ["kenyan_learning_samples.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_kenyan_learning_feedback_org_type",
        "kenyan_learning_feedback",
        ["organization_id", "feedback_type"],
        unique=False,
    )

    op.create_table(
        "kenyan_learning_training_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), server_default=sa.text("'queued'"), nullable=False),
        sa.Column(
            "targets",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
        sa.Column(
            "artifacts",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_kenyan_learning_runs_org_created",
        "kenyan_learning_training_runs",
        ["organization_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_kenyan_learning_runs_org_created", table_name="kenyan_learning_training_runs")
    op.drop_table("kenyan_learning_training_runs")
    op.drop_index("ix_kenyan_learning_feedback_org_type", table_name="kenyan_learning_feedback")
    op.drop_table("kenyan_learning_feedback")
    op.drop_index("ix_kenyan_learning_labels_org_status", table_name="kenyan_learning_label_tasks")
    op.drop_table("kenyan_learning_label_tasks")
    op.drop_index("ix_kenyan_learning_samples_created", table_name="kenyan_learning_samples")
    op.drop_index("ix_kenyan_learning_samples_org_target", table_name="kenyan_learning_samples")
    op.drop_table("kenyan_learning_samples")
