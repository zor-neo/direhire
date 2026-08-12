"""Add account scheduling and operational source controls.

Revision ID: 20260812_0006
Revises: 20260812_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0006"
down_revision: str | None = "20260812_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("job_watch_runs", sa.Column("schedule_date", sa.String(10)))
    op.create_index(
        "uq_scheduled_watch_day",
        "job_watch_runs",
        ["watch_id", "trigger", "schedule_date"],
        unique=True,
    )
    op.create_table(
        "user_schedules",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("local_time", sa.Time(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_schedules_next_run_at", "user_schedules", ["next_run_at"])
    policies = op.create_table(
        "source_policies",
        sa.Column("adapter_key", sa.String(64), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("health", sa.String(32), nullable=False),
        sa.Column("max_concurrency", sa.Integer(), nullable=False),
        sa.Column("minimum_delay_ms", sa.Integer(), nullable=False),
        sa.Column("browser_allowed", sa.Boolean(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("cooldown_until", sa.DateTime(timezone=True)),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.bulk_insert(
        policies,
        [
            {
                "adapter_key": "synthetic_board",
                "enabled": True,
                "health": "HEALTHY",
                "max_concurrency": 1,
                "minimum_delay_ms": 1000,
                "browser_allowed": False,
                "failure_count": 0,
            },
            {
                "adapter_key": "generic_public",
                "enabled": True,
                "health": "HEALTHY",
                "max_concurrency": 1,
                "minimum_delay_ms": 2000,
                "browser_allowed": False,
                "failure_count": 0,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("source_policies")
    op.drop_index("ix_user_schedules_next_run_at", table_name="user_schedules")
    op.drop_table("user_schedules")
    op.drop_index("uq_scheduled_watch_day", table_name="job_watch_runs")
    op.drop_column("job_watch_runs", "schedule_date")
