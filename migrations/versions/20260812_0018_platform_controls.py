"""add audited platform kill switches

Revision ID: 20260812_0018
Revises: 20260812_0017
Create Date: 2026-08-12
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0018"
down_revision: str | None = "20260812_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_controls",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    controls = sa.table(
        "platform_controls",
        sa.column("key", sa.String()),
        sa.column("enabled", sa.Boolean()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    op.bulk_insert(
        controls,
        [
            {"key": key, "enabled": True, "updated_at": now}
            for key in (
                "JOB_DISCOVERY",
                "MANUAL_RUN",
                "PUBLIC_AI",
                "PRIVATE_AI",
                "DOCUMENT_GENERATION",
                "TELEGRAM",
                "WHATSAPP",
                "BROWSER_SCRAPING",
            )
        ],
    )


def downgrade() -> None:
    op.drop_table("platform_controls")
