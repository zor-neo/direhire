"""add durable export and deletion workflows

Revision ID: 20260812_0011
Revises: 20260812_0010
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0011"
down_revision: str | None = "20260812_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_exports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("active_marker", sa.String(36), unique=True),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("private_files.id", ondelete="SET NULL")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_data_exports_user_id", "data_exports", ["user_id"])
    op.create_table(
        "deletion_workflows",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("scope", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("active_marker", sa.String(80), unique=True),
        sa.Column("error_code", sa.String(64)),
        sa.Column("progress", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_deletion_workflows_user_id", "deletion_workflows", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_deletion_workflows_user_id", table_name="deletion_workflows")
    op.drop_table("deletion_workflows")
    op.drop_index("ix_data_exports_user_id", table_name="data_exports")
    op.drop_table("data_exports")
