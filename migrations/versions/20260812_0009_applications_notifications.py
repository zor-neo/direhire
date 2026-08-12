"""add user applications and durable notifications

Revision ID: 20260812_0009
Revises: 20260812_0008
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0009"
down_revision: str | None = "20260812_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("applied_at", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "job_id", name="uq_user_application_job"),
    )
    op.create_index("ix_applications_user_status", "applications", ["user_id", "status"])
    op.create_table(
        "application_notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "application_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("note_type", sa.String(32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_application_notes_application_id", "application_notes", ["application_id"])
    op.create_table(
        "interview_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "application_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.String(24), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("questions_remembered", sa.Text()),
        sa.Column("went_well", sa.Text()),
        sa.Column("difficult", sa.Text()),
        sa.Column("other_notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_interview_records_application_id", "interview_records", ["application_id"])
    op.create_table(
        "reminders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "application_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reminder_type", sa.String(24), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reminders_application_id", "reminders", ["application_id"])
    op.create_index("ix_reminders_due", "reminders", ["completed_at", "due_at"])
    op.create_table(
        "notification_preferences",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("external_channel", sa.String(24), nullable=False),
        sa.Column("destination", sa.String(100)),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "notification_digests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("job_watch_runs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("matched_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notification_digests_user_id", "notification_digests", ["user_id"])
    op.create_table(
        "in_app_notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "digest_id",
            sa.String(36),
            sa.ForeignKey("notification_digests.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_in_app_notifications_user_id", "in_app_notifications", ["user_id"])
    op.create_table(
        "external_notification_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "digest_id",
            sa.String(36),
            sa.ForeignKey("notification_digests.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("destination", sa.String(100), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("provider_message_id", sa.String(200)),
        sa.Column("error_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("external_notification_deliveries")
    op.drop_index("ix_in_app_notifications_user_id", table_name="in_app_notifications")
    op.drop_table("in_app_notifications")
    op.drop_index("ix_notification_digests_user_id", table_name="notification_digests")
    op.drop_table("notification_digests")
    op.drop_table("notification_preferences")
    op.drop_index("ix_reminders_due", table_name="reminders")
    op.drop_index("ix_reminders_application_id", table_name="reminders")
    op.drop_table("reminders")
    op.drop_index("ix_interview_records_application_id", table_name="interview_records")
    op.drop_table("interview_records")
    op.drop_index("ix_application_notes_application_id", table_name="application_notes")
    op.drop_table("application_notes")
    op.drop_index("ix_applications_user_status", table_name="applications")
    op.drop_table("applications")
