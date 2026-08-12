from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from direhire.errors import AppError
from direhire.models import PlanEntitlement, UserEntitlementOverride

ACTIVE_WATCH_LIMIT = "active_watch_count"
MANUAL_RUN_DAILY_LIMIT = "manual_runs_per_day"
MANUAL_RUN_COOLDOWN_SECONDS = "manual_run_cooldown_seconds"
BASE_CV_LIMIT = "base_cv_count"
CV_SUGGESTION_MONTHLY_LIMIT = "cv_profile_suggestions_per_month"
PRIVATE_AI_DAILY_LIMIT = "private_ai_requests_per_day"
ANALYZE_JOB_MONTHLY_LIMIT = "analyze_job_requests_per_month"

SAFE_DEFAULT_LIMITS: dict[str, dict[str, int]] = {
    "FREE": {
        ACTIVE_WATCH_LIMIT: 3,
        MANUAL_RUN_DAILY_LIMIT: 1,
        MANUAL_RUN_COOLDOWN_SECONDS: 900,
        BASE_CV_LIMIT: 1,
        CV_SUGGESTION_MONTHLY_LIMIT: 1,
        PRIVATE_AI_DAILY_LIMIT: 0,
        ANALYZE_JOB_MONTHLY_LIMIT: 3,
    },
    "PREMIUM": {
        ACTIVE_WATCH_LIMIT: 10,
        MANUAL_RUN_DAILY_LIMIT: 5,
        MANUAL_RUN_COOLDOWN_SECONDS: 300,
        BASE_CV_LIMIT: 3,
        CV_SUGGESTION_MONTHLY_LIMIT: 10,
        PRIVATE_AI_DAILY_LIMIT: 20,
        ANALYZE_JOB_MONTHLY_LIMIT: 30,
    },
}


@dataclass(frozen=True, slots=True)
class EntitlementValue:
    enabled: bool
    limit_value: int
    source: str


class EntitlementService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def resolve(
        self,
        *,
        user_id: str,
        plan: str,
        entitlement_key: str,
        now: datetime | None = None,
    ) -> EntitlementValue:
        current_time = now or datetime.now(UTC)
        override = self.session.scalar(
            select(UserEntitlementOverride).where(
                UserEntitlementOverride.user_id == user_id,
                UserEntitlementOverride.entitlement_key == entitlement_key,
                UserEntitlementOverride.effective_from <= current_time,
                (UserEntitlementOverride.effective_until.is_(None))
                | (UserEntitlementOverride.effective_until > current_time),
            )
        )
        if override is not None:
            return EntitlementValue(override.enabled, override.limit_value, override.plan_source)
        configured = self.session.scalar(
            select(PlanEntitlement).where(
                PlanEntitlement.plan == plan,
                PlanEntitlement.entitlement_key == entitlement_key,
            )
        )
        if configured is not None:
            return EntitlementValue(configured.enabled, configured.limit_value, "plan")
        limit = SAFE_DEFAULT_LIMITS.get(plan, {}).get(entitlement_key, 0)
        return EntitlementValue(limit > 0, limit, "safe_default")

    def require_capacity(
        self,
        *,
        user_id: str,
        plan: str,
        entitlement_key: str,
        current_usage: int,
    ) -> EntitlementValue:
        value = self.resolve(user_id=user_id, plan=plan, entitlement_key=entitlement_key)
        if not value.enabled or current_usage >= value.limit_value:
            raise AppError(
                "QUOTA_EXCEEDED",
                "This feature has reached its current plan limit.",
                429,
            )
        return value
