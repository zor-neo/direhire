"""add outbox publication observability

Revision ID: 20260812_0017
Revises: 20260812_0016
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0017"
down_revision: str | None = "20260812_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column("publish_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("outbox_events", sa.Column("last_error_code", sa.String(64)))
    op.add_column("outbox_events", sa.Column("last_attempt_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("outbox_events", "last_attempt_at")
    op.drop_column("outbox_events", "last_error_code")
    op.drop_column("outbox_events", "publish_attempts")
