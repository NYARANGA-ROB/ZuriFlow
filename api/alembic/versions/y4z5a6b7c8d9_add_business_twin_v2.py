"""v2 twin: connector health, traces, unanswered questions, overrides, promotions

Revision ID: y4z5a6b7c8d9
Revises: x3y4z5a6b7c8
Create Date: 2026-08-24 08:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "y4z5a6b7c8d9"
down_revision: Union[str, None] = "x3y4z5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("business_faqs", sa.Column("language", sa.String(16), server_default="en", nullable=False))
    op.add_column("business_announcements", sa.Column("priority", sa.Integer(), server_default="0", nullable=False))
    op.add_column("business_announcements", sa.Column("location_id", sa.Integer(), nullable=True))
    op.add_column(
        "business_announcements",
        sa.Column("languages_json", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
    )
    op.add_column(
        "business_announcements",
        sa.Column("affected_services_json", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
    )
    op.add_column(
        "business_announcements",
        sa.Column("announcement_status", sa.String(32), server_default="active", nullable=False),
    )
    op.create_foreign_key(
        "fk_announcements_location",
        "business_announcements",
        "business_locations",
        ["location_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "business_data_sources",
        sa.Column("credentials_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
    )
    op.add_column(
        "business_data_sources",
        sa.Column("allowlisted_hosts_json", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
    )
    op.add_column(
        "business_data_sources",
        sa.Column("lifecycle_state", sa.String(32), server_default="discovered", nullable=False),
    )
    op.add_column("business_data_sources", sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("business_data_sources", sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("business_data_sources", sa.Column("last_failure_message", sa.Text(), nullable=True))
    op.add_column("business_data_sources", sa.Column("latency_ms", sa.Integer(), nullable=True))
    op.add_column("business_data_sources", sa.Column("error_rate", sa.Float(), server_default="0", nullable=False))
    op.add_column(
        "business_data_sources",
        sa.Column("auth_status", sa.String(32), server_default="unknown", nullable=False),
    )
    op.add_column(
        "business_data_sources",
        sa.Column("records_synced", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("business_data_changes", sa.Column("category", sa.String(32), nullable=True))
    op.add_column("business_knowledge_entries", sa.Column("language", sa.String(16), nullable=True))
    op.add_column("business_knowledge_entries", sa.Column("location_id", sa.Integer(), nullable=True))
    op.add_column(
        "business_knowledge_entries",
        sa.Column("is_approved", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )

    op.create_table(
        "business_agent_traces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(64), nullable=True),
        sa.Column("source_selected", sa.String(64), nullable=True),
        sa.Column("authority", sa.String(32), nullable=True),
        sa.Column("freshness", sa.Float(), nullable=True),
        sa.Column("tool_used", sa.String(64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("workflow_run_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_business_traces_org", "business_agent_traces", ["organization_id", "created_at"])

    op.create_table(
        "business_unanswered_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("question_redacted", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(64), nullable=True),
        sa.Column("missing_field", sa.String(64), nullable=True),
        sa.Column("hit_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_business_unanswered_org",
        "business_unanswered_questions",
        ["organization_id", "hit_count"],
    )

    op.create_table(
        "business_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("field_path", sa.String(255), nullable=False),
        sa.Column("source_value", sa.Text(), nullable=True),
        sa.Column("override_value", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
    )
    op.create_index("ix_business_overrides_org", "business_overrides", ["organization_id", "field_path"])

    op.create_table(
        "business_promotions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("discount", sa.String(64), nullable=True),
        sa.Column("applicable", sa.String(255), nullable=True),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eligibility", sa.Text(), nullable=True),
        sa.Column("promotion_status", sa.String(32), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(64), server_default="business_admin", nullable=False),
        sa.Column("source_type", sa.String(64), server_default="business_admin", nullable=False),
        sa.Column("source_reference", sa.String(512), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("freshness_score", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("status", sa.String(32), server_default="verified", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("provenance_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["business_locations.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_business_promotions_org", "business_promotions", ["organization_id"])


def downgrade() -> None:
    op.drop_table("business_promotions")
    op.drop_table("business_overrides")
    op.drop_table("business_unanswered_questions")
    op.drop_table("business_agent_traces")
    op.drop_column("business_knowledge_entries", "is_approved")
    op.drop_column("business_knowledge_entries", "location_id")
    op.drop_column("business_knowledge_entries", "language")
    op.drop_column("business_data_changes", "category")
    for col in (
        "records_synced",
        "auth_status",
        "error_rate",
        "latency_ms",
        "last_failure_message",
        "last_failure_at",
        "last_success_at",
        "lifecycle_state",
        "allowlisted_hosts_json",
        "credentials_json",
    ):
        op.drop_column("business_data_sources", col)
    op.drop_constraint("fk_announcements_location", "business_announcements", type_="foreignkey")
    for col in ("announcement_status", "affected_services_json", "languages_json", "location_id", "priority"):
        op.drop_column("business_announcements", col)
    op.drop_column("business_faqs", "language")
