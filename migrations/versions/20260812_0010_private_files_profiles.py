"""add private file quarantine, Base CV, and optional Profile

Revision ID: 20260812_0010
Revises: 20260812_0009
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0010"
down_revision: str | None = "20260812_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "private_files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("bucket", sa.String(100), nullable=False),
        sa.Column("object_key", sa.String(1024), nullable=False, unique=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("declared_content_type", sa.String(100), nullable=False),
        sa.Column("detected_content_type", sa.String(100)),
        sa.Column("declared_size", sa.Integer(), nullable=False),
        sa.Column("actual_size", sa.Integer()),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("rejection_code", sa.String(64)),
        sa.Column("scan_engine", sa.String(64)),
        sa.Column("scan_version", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_private_files_owner_status", "private_files", ["owner_id", "status"])
    op.create_table(
        "base_cvs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "file_id",
            sa.String(36),
            sa.ForeignKey("private_files.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_base_cvs_user_status", "base_cvs", ["user_id", "status"])
    op.create_table(
        "professional_profiles",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("headline", sa.String(300)),
        sa.Column("competencies", sa.JSON(), nullable=False),
        sa.Column("domain_knowledge", sa.JSON(), nullable=False),
        sa.Column("technologies_tools", sa.JSON(), nullable=False),
        sa.Column("languages", sa.JSON(), nullable=False),
        sa.Column("credentials_licenses", sa.JSON(), nullable=False),
        sa.Column("education", sa.JSON(), nullable=False),
        sa.Column("experience", sa.JSON(), nullable=False),
        sa.Column("eligibility_work_rights", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    competencies = op.create_table(
        "competency_catalog",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("source_mappings", sa.JSON(), nullable=False),
        sa.Column("parent_id", sa.String(100)),
    )
    op.bulk_insert(
        competencies,
        [
            {
                "id": "python",
                "display_name": "Python",
                "aliases": ["Python 3"],
                "source_mappings": {},
                "parent_id": None,
            },
            {
                "id": "postgresql",
                "display_name": "PostgreSQL",
                "aliases": ["Postgres"],
                "source_mappings": {},
                "parent_id": None,
            },
            {
                "id": "api-design",
                "display_name": "API design",
                "aliases": ["REST API design"],
                "source_mappings": {},
                "parent_id": None,
            },
        ],
    )
    occupations = op.create_table(
        "occupation_catalog",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("source_mappings", sa.JSON(), nullable=False),
        sa.Column("parent_id", sa.String(100)),
    )
    op.bulk_insert(
        occupations,
        [
            {
                "id": "software-engineer",
                "display_name": "Software Engineer",
                "aliases": ["Software Developer"],
                "source_mappings": {},
                "parent_id": None,
            },
            {
                "id": "backend-engineer",
                "display_name": "Backend Engineer",
                "aliases": ["Backend Developer"],
                "source_mappings": {},
                "parent_id": "software-engineer",
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("occupation_catalog")
    op.drop_table("competency_catalog")
    op.drop_table("professional_profiles")
    op.drop_index("ix_base_cvs_user_status", table_name="base_cvs")
    op.drop_table("base_cvs")
    op.drop_index("ix_private_files_owner_status", table_name="private_files")
    op.drop_table("private_files")
