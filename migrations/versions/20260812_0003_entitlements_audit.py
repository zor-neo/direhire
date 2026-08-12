"""Create configurable entitlements, account activity, and append-only audit.

Revision ID: 20260812_0003
Revises: 20260812_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0003"
down_revision: str | None = "20260812_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    plan_entitlements = op.create_table(
        "plan_entitlements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plan", sa.String(16), nullable=False),
        sa.Column("entitlement_key", sa.String(80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("limit_value", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("plan", "entitlement_key", name="uq_plan_entitlement"),
    )
    op.bulk_insert(
        plan_entitlements,
        [
            {
                "plan": "FREE",
                "entitlement_key": "active_watch_count",
                "enabled": True,
                "limit_value": 3,
            },
            {
                "plan": "FREE",
                "entitlement_key": "manual_runs_per_day",
                "enabled": True,
                "limit_value": 1,
            },
            {
                "plan": "PREMIUM",
                "entitlement_key": "active_watch_count",
                "enabled": True,
                "limit_value": 10,
            },
            {
                "plan": "PREMIUM",
                "entitlement_key": "manual_runs_per_day",
                "enabled": True,
                "limit_value": 5,
            },
        ],
    )
    op.create_table(
        "user_entitlement_overrides",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("entitlement_key", sa.String(80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("limit_value", sa.Integer(), nullable=False),
        sa.Column("plan_source", sa.String(32), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "entitlement_key", name="uq_user_entitlement_override"),
    )
    op.create_table(
        "account_activity",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("activity_type", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_account_activity_user_created", "account_activity", ["user_id", "created_at"]
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_user_id", sa.String(36)),
        sa.Column("actor_role", sa.String(16), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(128)),
        sa.Column("result", sa.String(16), nullable=False),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column("change_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_account_activity_user_created", table_name="account_activity")
    op.drop_table("account_activity")
    op.drop_table("user_entitlement_overrides")
    op.drop_table("plan_entitlements")
