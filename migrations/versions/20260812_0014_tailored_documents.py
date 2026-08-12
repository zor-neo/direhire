"""add versioned tailored CV documents

Revision ID: 20260812_0014
Revises: 20260812_0013
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0014"
down_revision: str | None = "20260812_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("private_ai_artifacts") as batch:
        batch.add_column(sa.Column("name", sa.String(160)))
        batch.add_column(
            sa.Column("version_number", sa.Integer(), nullable=False, server_default="1")
        )
        batch.add_column(sa.Column("parent_artifact_id", sa.String(36)))
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True)))
        batch.create_foreign_key(
            "fk_private_ai_parent",
            "private_ai_artifacts",
            ["parent_artifact_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_table(
        "tailored_cv_documents",
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
        sa.Column("format", sa.String(8), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("private_files.id", ondelete="SET NULL")),
        sa.Column("error_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "artifact_id", "format", "content_hash", name="uq_tailored_document_content"
        ),
    )
    op.create_index(
        "ix_tailored_documents_user_status",
        "tailored_cv_documents",
        ["user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_tailored_documents_user_status", table_name="tailored_cv_documents")
    op.drop_table("tailored_cv_documents")
    with op.batch_alter_table("private_ai_artifacts") as batch:
        batch.drop_constraint("fk_private_ai_parent", type_="foreignkey")
        batch.drop_column("archived_at")
        batch.drop_column("parent_artifact_id")
        batch.drop_column("version_number")
        batch.drop_column("name")
