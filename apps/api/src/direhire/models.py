from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Time,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from direhire.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class JobWatch(Base):
    __tablename__ = "job_watches"
    __table_args__ = (Index("ix_job_watches_owner_status", "owner_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    target_terms: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    required_terms: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    excluded_terms: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    locations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    raw_intent: Mapped[str | None] = mapped_column(String(2000))
    posting_age_days: Mapped[int | None] = mapped_column(nullable=True, default=30)
    work_arrangements: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    employment_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    experience_level: Mapped[str] = mapped_column(String(16), nullable=False, default="ANY")
    search_expansion: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sources: Mapped[list[WatchSource]] = relationship(
        back_populates="watch", cascade="all, delete-orphan", lazy="selectin"
    )


class WatchSource(Base):
    __tablename__ = "watch_sources"
    __table_args__ = (UniqueConstraint("watch_id", "source_key", name="uq_watch_source_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    watch_id: Mapped[str] = mapped_column(
        ForeignKey("job_watches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    platform_key: Mapped[str | None] = mapped_column(String(64))
    adapter_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source_key: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str | None] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    watch: Mapped[JobWatch] = relationship(back_populates="sources")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("cognito_subject", name="uq_users_cognito_subject"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cognito_subject: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="USER")
    plan: Mapped[str] = mapped_column(String(16), nullable=False, default="FREE")
    account_status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    security_version: Mapped[int] = mapped_column(nullable=False, default=1)
    mfa_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserSchedule(Base):
    __tablename__ = "user_schedules"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    local_time: Mapped[time] = mapped_column(Time(), nullable=False)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SourcePolicy(Base):
    __tablename__ = "source_policies"

    adapter_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    health: Mapped[str] = mapped_column(String(32), nullable=False, default="HEALTHY")
    max_concurrency: Mapped[int] = mapped_column(nullable=False, default=1)
    minimum_delay_ms: Mapped[int] = mapped_column(nullable=False, default=1000)
    browser_allowed: Mapped[bool] = mapped_column(nullable=False, default=False)
    failure_count: Mapped[int] = mapped_column(nullable=False, default=0)
    failure_threshold: Mapped[int] = mapped_column(nullable=False, default=3)
    cooldown_seconds: Mapped[int] = mapped_column(nullable=False, default=900)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
        Index("ix_auth_sessions_user_expires", "user_id", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    security_version: Mapped[int] = mapped_column(nullable=False)


class PlanEntitlement(Base):
    __tablename__ = "plan_entitlements"
    __table_args__ = (UniqueConstraint("plan", "entitlement_key", name="uq_plan_entitlement"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plan: Mapped[str] = mapped_column(String(16), nullable=False)
    entitlement_key: Mapped[str] = mapped_column(String(80), nullable=False)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    limit_value: Mapped[int] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserEntitlementOverride(Base):
    __tablename__ = "user_entitlement_overrides"
    __table_args__ = (
        UniqueConstraint("user_id", "entitlement_key", name="uq_user_entitlement_override"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    entitlement_key: Mapped[str] = mapped_column(String(80), nullable=False)
    enabled: Mapped[bool] = mapped_column(nullable=False)
    limit_value: Mapped[int] = mapped_column(nullable=False)
    plan_source: Mapped[str] = mapped_column(String(32), nullable=False, default="admin_grant")
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccountActivity(Base):
    __tablename__ = "account_activity"
    __table_args__ = (Index("ix_account_activity_user_created", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_created_at", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_user_id: Mapped[str | None] = mapped_column(String(36))
    actor_role: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(128))
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    change_metadata: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


@event.listens_for(AuditEvent, "before_update")
@event.listens_for(AuditEvent, "before_delete")
def _prevent_audit_mutation(*_: object) -> None:
    raise ValueError("audit events are append-only")


class JobWatchRun(Base):
    __tablename__ = "job_watch_runs"
    __table_args__ = (
        Index("ix_watch_runs_watch_status", "watch_id", "status"),
        UniqueConstraint("active_marker", name="uq_watch_runs_active_marker"),
        UniqueConstraint("watch_id", "trigger", "schedule_date", name="uq_scheduled_watch_day"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    watch_id: Mapped[str] = mapped_column(ForeignKey("job_watches.id", ondelete="CASCADE"))
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(16), nullable=False)
    schedule_date: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    # Equals watch_id while QUEUED/RUNNING and becomes null at a terminal state.
    # A nullable unique key makes click coalescing safe under concurrent requests.
    active_marker: Mapped[str | None] = mapped_column(String(36))
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(32))
    sources_succeeded: Mapped[int] = mapped_column(nullable=False, default=0)
    sources_failed: Mapped[int] = mapped_column(nullable=False, default=0)
    discovered_count: Mapped[int] = mapped_column(nullable=False, default=0)
    matched_count: Mapped[int] = mapped_column(nullable=False, default=0)


class SourceFetch(Base):
    __tablename__ = "source_fetches"
    __table_args__ = (UniqueConstraint("run_id", "watch_source_id", name="uq_run_source_fetch"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("job_watch_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    watch_source_id: Mapped[str] = mapped_column(
        ForeignKey("watch_sources.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    discovered_count: Mapped[int] = mapped_column(nullable=False, default=0)
    warning_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SharedSourceFetch(Base):
    __tablename__ = "shared_source_fetches"
    __table_args__ = (Index("ix_shared_source_fetch_status_lease", "status", "lease_expires_at"),)

    fetch_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    adapter_key: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_source: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="RUNNING")
    owner_run_id: Mapped[str | None] = mapped_column(String(36))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    results: Mapped[list[dict[str, object]] | None] = mapped_column(JSON)
    result_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("identity_key", name="uq_jobs_identity_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    identity_key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    company: Mapped[str] = mapped_column(String(300), nullable=False)
    location_raw: Mapped[str] = mapped_column(String(500), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JobVersion(Base):
    __tablename__ = "job_versions"
    __table_args__ = (UniqueConstraint("job_id", "content_hash", name="uq_job_version_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JobDemandProfile(Base):
    __tablename__ = "job_demand_profiles"
    __table_args__ = (
        UniqueConstraint(
            "job_version_id",
            "schema_version",
            "prompt_version",
            name="uq_job_analysis_version",
        ),
        Index("ix_job_demand_profiles_status", "status", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_version_id: Mapped[str] = mapped_column(
        ForeignKey("job_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    schema_version: Mapped[int] = mapped_column(nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    profile: Mapped[dict[str, object] | None] = mapped_column(JSON)
    operation_id: Mapped[str | None] = mapped_column(String(36))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AiModelPolicy(Base):
    __tablename__ = "ai_model_policies"
    __table_args__ = (UniqueConstraint("provider", "capability", name="uq_ai_provider_capability"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    capability: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    max_output_tokens: Mapped[int] = mapped_column(nullable=False)
    input_cost_microusd_per_million: Mapped[int] = mapped_column(nullable=False)
    output_cost_microusd_per_million: Mapped[int] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AiProviderRoute(Base):
    __tablename__ = "ai_provider_routes"

    route_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    health: Mapped[str] = mapped_column(String(32), nullable=False, default="HEALTHY")
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_requests: Mapped[int] = mapped_column(nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    consecutive_failures: Mapped[int] = mapped_column(nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AiOperation(Base):
    __tablename__ = "ai_operations"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ai_operation_idempotency"),
        Index("ix_ai_operations_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    task: Mapped[str] = mapped_column(String(64), nullable=False)
    capability: Mapped[str] = mapped_column(String(32), nullable=False)
    data_class: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    provider: Mapped[str | None] = mapped_column(String(32))
    route_key: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(100))
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    provider_attempts: Mapped[int] = mapped_column(nullable=False, default=0)
    estimated_cost_microusd: Mapped[int] = mapped_column(nullable=False, default=0)
    cache_hit: Mapped[bool] = mapped_column(nullable=False, default=False)
    latency_ms: Mapped[int] = mapped_column(nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceListing(Base):
    __tablename__ = "source_listings"
    __table_args__ = (UniqueConstraint("adapter_key", "external_id", name="uq_source_listing"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    adapter_key: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(300), nullable=False)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WatchMatch(Base):
    __tablename__ = "watch_matches"
    __table_args__ = (UniqueConstraint("run_id", "watch_id", "job_id", name="uq_watch_run_job"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("job_watch_runs.id", ondelete="CASCADE"), nullable=False
    )
    watch_id: Mapped[str] = mapped_column(
        ForeignKey("job_watches.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserJob(Base):
    __tablename__ = "user_jobs"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_user_job"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="NEW")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_user_application_job"),
        Index("ix_applications_user_status", "user_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="APPLIED")
    applied_at: Mapped[date | None] = mapped_column(Date())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApplicationNote(Base):
    __tablename__ = "application_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    note_type: Mapped[str] = mapped_column(String(32), nullable=False)
    body: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InterviewRecord(Base):
    __tablename__ = "interview_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(24), nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    questions_remembered: Mapped[str | None] = mapped_column(Text())
    went_well: Mapped[str | None] = mapped_column(Text())
    difficult: Mapped[str | None] = mapped_column(Text())
    other_notes: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (Index("ix_reminders_due", "completed_at", "due_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reminder_type: Mapped[str] = mapped_column(String(24), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    external_channel: Mapped[str] = mapped_column(String(24), nullable=False, default="NONE")
    destination: Mapped[str | None] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NotificationDigest(Base):
    __tablename__ = "notification_digests"
    __table_args__ = (UniqueConstraint("run_id", name="uq_notification_digest_run"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("job_watch_runs.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    matched_count: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InAppNotification(Base):
    __tablename__ = "in_app_notifications"
    __table_args__ = (UniqueConstraint("digest_id", name="uq_in_app_notification_digest"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    digest_id: Mapped[str] = mapped_column(
        ForeignKey("notification_digests.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(String(1000), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExternalNotificationDelivery(Base):
    __tablename__ = "external_notification_deliveries"
    __table_args__ = (UniqueConstraint("digest_id", name="uq_external_delivery_digest"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    digest_id: Mapped[str] = mapped_column(
        ForeignKey("notification_digests.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(24), nullable=False)
    destination: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="QUEUED")
    attempts: Mapped[int] = mapped_column(nullable=False, default=0)
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PrivateFile(Base):
    __tablename__ = "private_files"
    __table_args__ = (Index("ix_private_files_owner_status", "owner_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    bucket: Mapped[str] = mapped_column(String(100), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    declared_content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    detected_content_type: Mapped[str | None] = mapped_column(String(100))
    declared_size: Mapped[int] = mapped_column(nullable=False)
    actual_size: Mapped[int | None] = mapped_column()
    content_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="UPLOADING")
    rejection_code: Mapped[str | None] = mapped_column(String(64))
    scan_engine: Mapped[str | None] = mapped_column(String(64))
    scan_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BaseCv(Base):
    __tablename__ = "base_cvs"
    __table_args__ = (Index("ix_base_cvs_user_status", "user_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    file_id: Mapped[str] = mapped_column(
        ForeignKey("private_files.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="UPLOADING")
    extraction_status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    extracted_text: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProfessionalProfile(Base):
    __tablename__ = "professional_profiles"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    headline: Mapped[str | None] = mapped_column(String(300))
    competencies: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    domain_knowledge: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    technologies_tools: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    languages: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    credentials_licenses: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    education: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    experience: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    eligibility_work_rights: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CompetencyCatalog(Base):
    __tablename__ = "competency_catalog"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_mappings: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    parent_id: Mapped[str | None] = mapped_column(String(100))


class OccupationCatalog(Base):
    __tablename__ = "occupation_catalog"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_mappings: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    parent_id: Mapped[str | None] = mapped_column(String(100))


class DataExport(Base):
    __tablename__ = "data_exports"
    __table_args__ = (UniqueConstraint("active_marker", name="uq_active_user_export"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="QUEUED")
    active_marker: Mapped[str | None] = mapped_column(String(36))
    file_id: Mapped[str | None] = mapped_column(ForeignKey("private_files.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeletionWorkflow(Base):
    __tablename__ = "deletion_workflows"
    __table_args__ = (UniqueConstraint("active_marker", name="uq_active_deletion_workflow"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="QUEUED")
    active_marker: Mapped[str | None] = mapped_column(String(80))
    error_code: Mapped[str | None] = mapped_column(String(64))
    progress: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PrivateAiArtifact(Base):
    __tablename__ = "private_ai_artifacts"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_private_ai_artifact_idempotency"),
        Index("ix_private_ai_artifacts_user_type", "user_id", "artifact_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"))
    cv_id: Mapped[str | None] = mapped_column(ForeignKey("base_cvs.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    content: Mapped[dict[str, object] | None] = mapped_column(JSON)
    working_draft: Mapped[dict[str, object] | None] = mapped_column(JSON)
    operation_id: Mapped[str | None] = mapped_column(String(36))
    error_code: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str | None] = mapped_column(String(160))
    version_number: Mapped[int] = mapped_column(nullable=False, default=1)
    parent_artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("private_ai_artifacts.id", ondelete="SET NULL")
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProfileSuggestion(Base):
    __tablename__ = "profile_suggestions"
    __table_args__ = (Index("ix_profile_suggestions_user_status", "user_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    artifact_id: Mapped[str] = mapped_column(
        ForeignKey("private_ai_artifacts.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    suggestion: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TailoredCvDocument(Base):
    __tablename__ = "tailored_cv_documents"
    __table_args__ = (
        UniqueConstraint(
            "artifact_id", "format", "content_hash", name="uq_tailored_document_content"
        ),
        Index("ix_tailored_documents_user_status", "user_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    artifact_id: Mapped[str] = mapped_column(
        ForeignKey("private_ai_artifacts.id", ondelete="CASCADE"), nullable=False
    )
    format: Mapped[str] = mapped_column(String(8), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="QUEUED")
    file_id: Mapped[str | None] = mapped_column(ForeignKey("private_files.id", ondelete="SET NULL"))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdHocJobAnalysis(Base):
    __tablename__ = "ad_hoc_job_analyses"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ad_hoc_analysis_idempotency"),
        Index("ix_ad_hoc_analyses_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    input_type: Mapped[str] = mapped_column(String(16), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_url: Mapped[str | None] = mapped_column(String(2048))
    private_text: Mapped[str | None] = mapped_column(Text())
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"))
    demand_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("job_demand_profiles.id", ondelete="SET NULL")
    )
    private_artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("private_ai_artifacts.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_outbox_event_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(40), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[int] = mapped_column(nullable=False, default=1)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publish_attempts: Mapped[int] = mapped_column(nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlatformControl(Base):
    __tablename__ = "platform_controls"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
