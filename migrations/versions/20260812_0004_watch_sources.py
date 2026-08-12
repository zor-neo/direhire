"""Expand Watch configuration and add owned source selections.

Revision ID: 20260812_0004
Revises: 20260812_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0004"
down_revision: str | None = "20260812_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "job_watches",
        sa.Column("work_arrangements", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "job_watches",
        sa.Column("employment_types", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column("job_watches", sa.Column("experience_target", sa.String(64)))
    op.create_table(
        "watch_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "watch_id",
            sa.String(36),
            sa.ForeignKey("job_watches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_kind", sa.String(24), nullable=False),
        sa.Column("adapter_key", sa.String(64), nullable=False),
        sa.Column("source_key", sa.String(512), nullable=False),
        sa.Column("url", sa.String(2048)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("watch_id", "source_key", name="uq_watch_source_key"),
    )
    op.create_index("ix_watch_sources_watch_id", "watch_sources", ["watch_id"])


def downgrade() -> None:
    op.drop_index("ix_watch_sources_watch_id", table_name="watch_sources")
    op.drop_table("watch_sources")
    op.drop_column("job_watches", "experience_target")
    op.drop_column("job_watches", "employment_types")
    op.drop_column("job_watches", "work_arrangements")
