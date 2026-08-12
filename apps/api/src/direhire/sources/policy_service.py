from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from direhire.models import SourcePolicy, utcnow


class SourcePolicyService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create(self, adapter_key: str) -> SourcePolicy:
        policy = self.session.get(SourcePolicy, adapter_key)
        if policy is None:
            policy = SourcePolicy(adapter_key=adapter_key)
            self.session.add(policy)
            self.session.flush()
        return policy

    def unavailable_code(self, adapter_key: str, *, now: datetime | None = None) -> str | None:
        policy = self.session.get(SourcePolicy, adapter_key)
        if policy is None:
            return None
        if not policy.enabled:
            return "SOURCE_DISABLED"
        current_time = now or datetime.now(UTC)
        cooldown_until = policy.cooldown_until
        if cooldown_until is not None and cooldown_until.tzinfo is None:
            cooldown_until = cooldown_until.replace(tzinfo=UTC)
        if policy.health == "TEMPORARILY_PAUSED":
            if cooldown_until is not None and cooldown_until <= current_time:
                policy.health = "DEGRADED"
                policy.cooldown_until = None
                policy.updated_at = current_time
                return None
            return "SOURCE_PAUSED"
        return None

    def record_success(self, adapter_key: str) -> SourcePolicy:
        policy = self.get_or_create(adapter_key)
        policy.failure_count = 0
        policy.cooldown_until = None
        if policy.enabled:
            policy.health = "HEALTHY"
        policy.updated_at = utcnow()
        return policy

    def record_failure(self, adapter_key: str) -> SourcePolicy:
        policy = self.get_or_create(adapter_key)
        policy.failure_count += 1
        policy.health = "DEGRADED"
        if policy.failure_count >= policy.failure_threshold:
            policy.health = "TEMPORARILY_PAUSED"
            policy.cooldown_until = utcnow() + timedelta(seconds=policy.cooldown_seconds)
        policy.updated_at = utcnow()
        return policy
