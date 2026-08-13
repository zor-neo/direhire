"""Watch experience level enum and search expansion.

Revision ID: 20260813_0019
Revises: 20260812_0018
"""

import sqlalchemy as sa
from alembic import op

revision = "20260813_0019"
down_revision = "20260812_0018"


def upgrade() -> None:
    # Expand/contract: new code reads experience_level while the previous
    # release can continue reading experience_target during deployment overlap.
    op.add_column(
        "job_watches",
        sa.Column("experience_level", sa.String(16), nullable=False, server_default="ANY"),
    )
    op.execute(
        "UPDATE job_watches SET experience_level = "
        "CASE "
        "WHEN UPPER(TRIM(experience_target)) IN ('ENTRY', 'ENTRY LEVEL', 'ENTRY-LEVEL') "
        "THEN 'ENTRY' "
        "WHEN UPPER(TRIM(experience_target)) = 'JUNIOR' THEN 'JUNIOR' "
        "WHEN UPPER(TRIM(experience_target)) IN ('MID', 'MID LEVEL', 'MID-LEVEL') THEN 'MID' "
        "WHEN UPPER(TRIM(experience_target)) = 'SENIOR' THEN 'SENIOR' "
        "WHEN UPPER(TRIM(experience_target)) = 'LEAD' THEN 'LEAD' "
        "WHEN UPPER(TRIM(experience_target)) IN ('EXECUTIVE', 'DIRECTOR', 'C-SUITE') "
        "THEN 'EXECUTIVE' "
        "ELSE 'ANY' END"
    )

    op.add_column(
        "job_watches",
        sa.Column("search_expansion", sa.JSON, nullable=True),
    )
    op.add_column(
        "watch_sources",
        sa.Column("platform_key", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("watch_sources", "platform_key")
    op.drop_column("job_watches", "search_expansion")
    op.drop_column("job_watches", "experience_level")
