"""Create canonical job corpus and durable discovery results.

Revision ID: 20260812_0005
Revises: 20260812_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0005"
down_revision: str | None = "20260812_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column in (
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("outcome", sa.String(32)),
        sa.Column("sources_succeeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sources_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discovered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default="0"),
    ):
        op.add_column("job_watch_runs", column)

    op.create_table(
        "source_fetches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("job_watch_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "watch_source_id",
            sa.String(36),
            sa.ForeignKey("watch_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("discovered_count", sa.Integer(), nullable=False),
        sa.Column("warning_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "watch_source_id", name="uq_run_source_fetch"),
    )
    op.create_index("ix_source_fetches_run_id", "source_fetches", ["run_id"])
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("identity_key", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("company", sa.String(300), nullable=False),
        sa.Column("location_raw", sa.String(500), nullable=False),
        sa.Column("lifecycle_status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "job_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "content_hash", name="uq_job_version_hash"),
    )
    op.create_table(
        "source_listings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("adapter_key", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(300), nullable=False),
        sa.Column(
            "job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("adapter_key", "external_id", name="uq_source_listing"),
    )
    op.create_table(
        "watch_matches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("job_watch_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "watch_id",
            sa.String(36),
            sa.ForeignKey("job_watches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "watch_id", "job_id", name="uq_watch_run_job"),
    )
    op.create_table(
        "user_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "job_id", name="uq_user_job"),
    )


def downgrade() -> None:
    op.drop_table("user_jobs")
    op.drop_table("watch_matches")
    op.drop_table("source_listings")
    op.drop_table("job_versions")
    op.drop_table("jobs")
    op.drop_index("ix_source_fetches_run_id", table_name="source_fetches")
    op.drop_table("source_fetches")
    for column in (
        "matched_count",
        "discovered_count",
        "sources_failed",
        "sources_succeeded",
        "outcome",
        "completed_at",
    ):
        op.drop_column("job_watch_runs", column)
