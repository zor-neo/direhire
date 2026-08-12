"""add configurable source circuit controls

Revision ID: 20260812_0007
Revises: 20260812_0006
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0007"
down_revision: str | None = "20260812_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "source_policies",
        sa.Column("failure_threshold", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "source_policies",
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="900"),
    )


def downgrade() -> None:
    op.drop_column("source_policies", "cooldown_seconds")
    op.drop_column("source_policies", "failure_threshold")
