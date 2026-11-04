"""add business digital twin and live operations tables

Revision ID: x3y4z5a6b7c8
Revises: w2x3y4z5a6b7
Create Date: 2026-08-24 08:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "x3y4z5a6b7c8"
down_revision: Union[str, None] = "w2x3y4z5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _prov(table: str) -> None:
    op.add_column(table, sa.Column("source", sa.String(length=64), server_default="business_admin", nullable=False))
    op.add_column(table, sa.Column("source_type", sa.String(length=64), server_default="business_admin", nullable=False))
    op.add_column(table, sa.Column("source_reference", sa.String(length=512), nullable=True))
    op.add_column(table, sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("freshness_score", sa.Float(), server_default="1.0", nullable=False))
    op.add_column(table, sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False))
    op.add_column(table, sa.Column("status", sa.String(length=32), server_default="verified", nullable=False))
    op.add_column(table, sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    op.add_column(
        table,
        sa.Column("provenance_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
    )


def upgrade() -> None:
    _prov("business_knowledge_entries")

    op.create_table(
        "business_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("legal_name", sa.String(255), nullable=True),
        sa.Column("trading_name", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("industry", sa.String(64), nullable=True),
        sa.Column("sub_industry", sa.String(64), nullable=True),
        sa.Column("website", sa.String(512), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phones_json", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
        sa.Column("counties_json", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
        sa.Column("service_areas_json", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
        sa.Column("social_channels_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("languages_json", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
        sa.Column("hours_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("payment_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("operational_refs_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("organization_id", name="uq_business_profiles_org"),
    )
    _prov("business_profiles")
    op.create_index("ix_business_profiles_org", "business_profiles", ["organization_id"])

    op.create_table(
        "business_locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("county", sa.String(64), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("is_branch", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("hours_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    _prov("business_locations")
    op.create_index("ix_business_locations_org", "business_locations", ["organization_id"])

    op.create_table(
        "business_hours",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("weekday", sa.String(16), nullable=False),
        sa.Column("open_time", sa.String(8), nullable=True),
        sa.Column("close_time", sa.String(8), nullable=True),
        sa.Column("is_closed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("kind", sa.String(32), server_default="regular", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["business_locations.id"], ondelete="CASCADE"),
    )
    _prov("business_hours")
    op.create_index("ix_business_hours_org", "business_hours", ["organization_id"])

    op.create_table(
        "business_holidays",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("holiday_date", sa.String(16), nullable=False),
        sa.Column("is_closed", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    _prov("business_holidays")
    op.create_index("ix_business_holidays_org", "business_holidays", ["organization_id"])

    op.create_table(
        "business_offerings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_amount", sa.Float(), nullable=True),
        sa.Column("price_currency", sa.String(8), server_default="KES", nullable=False),
        sa.Column("sku", sa.String(64), nullable=True),
        sa.Column("is_live_priced", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("live_source_key", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    _prov("business_offerings")
    op.create_index("ix_business_offerings_org_kind", "business_offerings", ["organization_id", "kind"])

    op.create_table(
        "business_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), server_default="", nullable=False),
        sa.Column("policy_type", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    _prov("business_policies")
    op.create_index("ix_business_policies_org", "business_policies", ["organization_id"])

    op.create_table(
        "business_faqs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    _prov("business_faqs")
    op.create_index("ix_business_faqs_org", "business_faqs", ["organization_id"])

    op.create_table(
        "business_contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(128), nullable=True),
        sa.Column("department", sa.String(128), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("is_escalation", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    _prov("business_contacts")
    op.create_index("ix_business_contacts_org", "business_contacts", ["organization_id"])

    op.create_table(
        "business_announcements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    _prov("business_announcements")
    op.create_index("ix_business_announcements_org", "business_announcements", ["organization_id"])

    op.create_table(
        "business_data_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("provider_kind", sa.String(64), nullable=False),
        sa.Column("adapter_key", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("schedule", sa.String(32), server_default="daily", nullable=False),
        sa.Column("is_live", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("webhook_secret", sa.String(128), nullable=True),
        sa.Column("config_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_business_data_sources_org", "business_data_sources", ["organization_id"])

    op.create_table(
        "business_data_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("record_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["business_data_sources.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_business_snapshots_org_source",
        "business_data_snapshots",
        ["organization_id", "source_id"],
    )

    op.create_table(
        "business_data_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("field_path", sa.String(255), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("risk_level", sa.String(16), server_default="medium", nullable=False),
        sa.Column("status", sa.String(32), server_default="detected", nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_business_changes_org_status",
        "business_data_changes",
        ["organization_id", "status"],
    )

    op.create_table(
        "business_conflicts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("field_path", sa.String(255), nullable=False),
        sa.Column("source_a", sa.String(64), nullable=False),
        sa.Column("value_a", sa.Text(), nullable=True),
        sa.Column("source_b", sa.String(64), nullable=False),
        sa.Column("value_b", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_status", sa.String(32), server_default="open", nullable=False),
        sa.Column("resolved_source", sa.String(64), nullable=True),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"]),
    )
    op.create_index(
        "ix_business_conflicts_org",
        "business_conflicts",
        ["organization_id", "resolution_status"],
    )

    op.create_table(
        "business_sync_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("schedule", sa.String(32), server_default="daily", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("lock_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["business_data_sources.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_business_sync_jobs_next", "business_sync_jobs", ["enabled", "next_run_at"])

    op.create_table(
        "business_sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_discovered", sa.Integer(), server_default="0", nullable=False),
        sa.Column("records_changed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("records_failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("conflicts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), server_default="running", nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["business_sync_jobs.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_business_sync_runs_org",
        "business_sync_runs",
        ["organization_id", "started_at"],
    )

    op.create_table(
        "business_sync_errors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("detail_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["business_sync_runs.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "business_approvals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("change_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=True),
        sa.Column("decision", sa.String(16), server_default="pending", nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["change_id"], ["business_data_changes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"]),
    )
    op.create_index(
        "ix_business_approvals_org",
        "business_approvals",
        ["organization_id", "decision"],
    )

    op.create_table(
        "business_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("payload_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("processed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_business_events_org_type",
        "business_events",
        ["organization_id", "event_type"],
    )

    op.create_table(
        "business_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(16), server_default="warning", nullable=False),
        sa.Column("action_url", sa.String(255), nullable=True),
        sa.Column("is_open", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_business_alerts_org_open", "business_alerts", ["organization_id", "is_open"])

    op.create_table(
        "business_field_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("field_path", sa.String(255), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
    )
    op.create_index(
        "ix_business_field_versions_entity",
        "business_field_versions",
        ["organization_id", "entity_type", "entity_id", "field_path"],
    )

    op.create_table(
        "business_source_authority",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("data_type", sa.String(64), nullable=False),
        sa.Column("ranked_sources_json", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("organization_id", "data_type", name="uq_business_source_authority"),
    )

    op.create_table(
        "business_interview_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("transcript", sa.Text(), server_default="", nullable=False),
        sa.Column("extracted_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("status", sa.String(32), server_default="draft", nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_business_interview_org", "business_interview_sessions", ["organization_id"])


def downgrade() -> None:
    for table in (
        "business_interview_sessions",
        "business_source_authority",
        "business_field_versions",
        "business_alerts",
        "business_events",
        "business_approvals",
        "business_sync_errors",
        "business_sync_runs",
        "business_sync_jobs",
        "business_conflicts",
        "business_data_changes",
        "business_data_snapshots",
        "business_data_sources",
        "business_announcements",
        "business_contacts",
        "business_faqs",
        "business_policies",
        "business_offerings",
        "business_holidays",
        "business_hours",
        "business_locations",
        "business_profiles",
    ):
        op.drop_table(table)
    for col in (
        "provenance_json",
        "version",
        "status",
        "confidence",
        "freshness_score",
        "expires_at",
        "last_changed_at",
        "last_seen_at",
        "last_verified_at",
        "source_reference",
        "source_type",
        "source",
    ):
        op.drop_column("business_knowledge_entries", col)
