"""Watch experience level enum and search expansion.

Revision ID: 20260813_0019
Revises: 20260812_0018
"""

import sqlalchemy as sa
from alembic import op

revision = "20260813_0019"
down_revision = "20260812_0018"


def upgrade() -> None:
    # Expand/contract: add new column, backfill from old, drop old.
    # Safe pre-production since no live user data exists yet.
    op.add_column(
        "job_watches",
        sa.Column("experience_level", sa.String(16), nullable=False, server_default="ANY"),
    )
    op.execute(
        "UPDATE job_watches SET experience_level = "
        "CASE WHEN experience_target IS NOT NULL THEN experience_target ELSE 'ANY' END"
    )
    op.drop_column("job_watches", "experience_target")

    op.add_column(
        "job_watches",
        sa.Column("search_expansion", sa.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("job_watches", "search_expansion")

    op.add_column(
        "job_watches",
        sa.Column("experience_target", sa.String(64), nullable=True),
    )
    op.execute(
        "UPDATE job_watches SET experience_target = "
        "CASE WHEN experience_level != 'ANY' THEN experience_level ELSE NULL END"
    )
    op.drop_column("job_watches", "experience_level")
