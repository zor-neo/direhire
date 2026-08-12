"""add CV extraction and private AI artifact workflow

Revision ID: 20260812_0013
Revises: 20260812_0012
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0013"
down_revision: str | None = "20260812_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "base_cvs",
        sa.Column("extraction_status", sa.String(24), nullable=False, server_default="PENDING"),
    )
    op.add_column("base_cvs", sa.Column("extracted_text", sa.Text()))
    op.create_table(
        "private_ai_artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("artifact_type", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="RESTRICT")),
        sa.Column("cv_id", sa.String(36), sa.ForeignKey("base_cvs.id", ondelete="CASCADE")),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("content", sa.JSON()),
        sa.Column("working_draft", sa.JSON()),
        sa.Column("operation_id", sa.String(36)),
        sa.Column("error_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_private_ai_artifacts_user_type",
        "private_ai_artifacts",
        ["user_id", "artifact_type"],
    )
    op.create_table(
        "profile_suggestions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "artifact_id",
            sa.String(36),
            sa.ForeignKey("private_ai_artifacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("suggestion", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_profile_suggestions_user_status",
        "profile_suggestions",
        ["user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_profile_suggestions_user_status", table_name="profile_suggestions")
    op.drop_table("profile_suggestions")
    op.drop_index("ix_private_ai_artifacts_user_type", table_name="private_ai_artifacts")
    op.drop_table("private_ai_artifacts")
    op.drop_column("base_cvs", "extracted_text")
    op.drop_column("base_cvs", "extraction_status")
