"""add approved private AI model and route policy

Revision ID: 20260812_0012
Revises: 20260812_0011
Create Date: 2026-08-12
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0012"
down_revision: str | None = "20260812_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    policies = sa.table(
        "ai_model_policies",
        sa.column("provider", sa.String()),
        sa.column("capability", sa.String()),
        sa.column("model", sa.String()),
        sa.column("enabled", sa.Boolean()),
        sa.column("max_output_tokens", sa.Integer()),
        sa.column("input_cost_microusd_per_million", sa.Integer()),
        sa.column("output_cost_microusd_per_million", sa.Integer()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        policies,
        [
            {
                "provider": "OPENROUTER",
                "capability": capability,
                "model": "anthropic/claude-sonnet-4.5",
                "enabled": True,
                "max_output_tokens": output_tokens,
                "input_cost_microusd_per_million": 3_000_000,
                "output_cost_microusd_per_million": 15_000_000,
                "updated_at": datetime.now(UTC),
            }
            for capability, output_tokens in (
                ("AI_STANDARD", 4096),
                ("AI_DEEP_REASONING", 6144),
                ("AI_DOCUMENT", 8192),
            )
        ],
    )
    routes = sa.table(
        "ai_provider_routes",
        sa.column("route_key", sa.String()),
        sa.column("provider", sa.String()),
        sa.column("enabled", sa.Boolean()),
        sa.column("health", sa.String()),
        sa.column("total_requests", sa.Integer()),
        sa.column("total_tokens", sa.Integer()),
        sa.column("consecutive_failures", sa.Integer()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        routes,
        [
            {
                "route_key": "openrouter-private",
                "provider": "OPENROUTER",
                "enabled": True,
                "health": "HEALTHY",
                "total_requests": 0,
                "total_tokens": 0,
                "consecutive_failures": 0,
                "updated_at": datetime.now(UTC),
            }
        ],
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM ai_provider_routes WHERE route_key = 'openrouter-private'"))
    op.execute(sa.text("DELETE FROM ai_model_policies WHERE provider = 'OPENROUTER'"))
