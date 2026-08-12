"""add shared public source fetch coalescing

Revision ID: 20260812_0016
Revises: 20260812_0015
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0016"
down_revision: str | None = "20260812_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shared_source_fetches",
        sa.Column("fetch_key", sa.String(64), primary_key=True),
        sa.Column("adapter_key", sa.String(64), nullable=False),
        sa.Column("normalized_source", sa.String(2048), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("owner_run_id", sa.String(36)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("results", sa.JSON()),
        sa.Column("result_expires_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_shared_source_fetch_status_lease",
        "shared_source_fetches",
        ["status", "lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_shared_source_fetch_status_lease", table_name="shared_source_fetches")
    op.drop_table("shared_source_fetches")
