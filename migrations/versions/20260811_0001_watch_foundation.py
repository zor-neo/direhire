"""Create Watch, run, and outbox foundation.

Revision ID: 20260811_0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_watches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("target_terms", sa.JSON(), nullable=False),
        sa.Column("required_terms", sa.JSON(), nullable=False),
        sa.Column("excluded_terms", sa.JSON(), nullable=False),
        sa.Column("locations", sa.JSON(), nullable=False),
        sa.Column("raw_intent", sa.String(2000)),
        sa.Column("posting_age_days", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_job_watches_owner_id", "job_watches", ["owner_id"])
    op.create_index("ix_job_watches_owner_status", "job_watches", ["owner_id", "status"])
    op.create_table(
        "job_watch_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("watch_id", sa.String(36), sa.ForeignKey("job_watches.id", ondelete="CASCADE")),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("trigger", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("active_marker", sa.String(36)),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("active_marker", name="uq_watch_runs_active_marker"),
    )
    op.create_index("ix_job_watch_runs_owner_id", "job_watch_runs", ["owner_id"])
    op.create_index("ix_watch_runs_watch_status", "job_watch_runs", ["watch_id", "status"])
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(40), nullable=False, unique=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_index("ix_watch_runs_watch_status", table_name="job_watch_runs")
    op.drop_index("ix_job_watch_runs_owner_id", table_name="job_watch_runs")
    op.drop_table("job_watch_runs")
    op.drop_index("ix_job_watches_owner_status", table_name="job_watches")
    op.drop_index("ix_job_watches_owner_id", table_name="job_watches")
    op.drop_table("job_watches")
