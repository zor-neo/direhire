"""add structured public AI analysis and metering

Revision ID: 20260812_0008
Revises: 20260812_0007
Create Date: 2026-08-12
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0008"
down_revision: str | None = "20260812_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_demand_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "job_version_id",
            sa.String(36),
            sa.ForeignKey("job_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("profile", sa.JSON()),
        sa.Column("operation_id", sa.String(36)),
        sa.Column("error_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "job_version_id",
            "schema_version",
            "prompt_version",
            name="uq_job_analysis_version",
        ),
    )
    op.create_index(
        "ix_job_demand_profiles_job_version_id", "job_demand_profiles", ["job_version_id"]
    )
    op.create_index(
        "ix_job_demand_profiles_status", "job_demand_profiles", ["status", "updated_at"]
    )
    policies = op.create_table(
        "ai_model_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("capability", sa.String(32), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("input_cost_microusd_per_million", sa.Integer(), nullable=False),
        sa.Column("output_cost_microusd_per_million", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "capability", name="uq_ai_provider_capability"),
    )
    op.bulk_insert(
        policies,
        [
            {
                "provider": "GEMINI",
                "capability": "AI_STANDARD",
                "model": "gemini-3.6-flash",
                "enabled": True,
                "max_output_tokens": 4096,
                "input_cost_microusd_per_million": 1_500_000,
                "output_cost_microusd_per_million": 7_500_000,
                "updated_at": datetime.now(UTC),
            }
        ],
    )
    routes = op.create_table(
        "ai_provider_routes",
        sa.Column("route_key", sa.String(64), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("health", sa.String(32), nullable=False),
        sa.Column("cooldown_until", sa.DateTime(timezone=True)),
        sa.Column("total_requests", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(64)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.bulk_insert(
        routes,
        [
            {
                "route_key": route,
                "provider": "GEMINI",
                "enabled": True,
                "health": "HEALTHY",
                "total_requests": 0,
                "total_tokens": 0,
                "consecutive_failures": 0,
                "updated_at": datetime.now(UTC),
            }
            for route in ("project-a", "project-b", "project-c")
        ],
    )
    op.create_table(
        "ai_operations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(160), nullable=False, unique=True),
        sa.Column("task", sa.String(64), nullable=False),
        sa.Column("capability", sa.String(32), nullable=False),
        sa.Column("data_class", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(32)),
        sa.Column("route_key", sa.String(64)),
        sa.Column("model", sa.String(100)),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("provider_attempts", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_microusd", sa.Integer(), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_ai_operations_status_created", "ai_operations", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_operations_status_created", table_name="ai_operations")
    op.drop_table("ai_operations")
    op.drop_table("ai_provider_routes")
    op.drop_table("ai_model_policies")
    op.drop_index("ix_job_demand_profiles_status", table_name="job_demand_profiles")
    op.drop_index("ix_job_demand_profiles_job_version_id", table_name="job_demand_profiles")
    op.drop_table("job_demand_profiles")
