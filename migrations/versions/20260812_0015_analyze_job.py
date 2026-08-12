"""add Analyze-a-Job workflow

Revision ID: 20260812_0015
Revises: 20260812_0014
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0015"
down_revision: str | None = "20260812_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ad_hoc_job_analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("input_type", sa.String(16), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("normalized_url", sa.String(2048)),
        sa.Column("private_text", sa.Text()),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="RESTRICT")),
        sa.Column(
            "demand_profile_id",
            sa.String(36),
            sa.ForeignKey("job_demand_profiles.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "private_artifact_id",
            sa.String(36),
            sa.ForeignKey("private_ai_artifacts.id", ondelete="CASCADE"),
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("saved_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_ad_hoc_analyses_user_created",
        "ad_hoc_job_analyses",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ad_hoc_analyses_user_created", table_name="ad_hoc_job_analyses")
    op.drop_table("ad_hoc_job_analyses")
