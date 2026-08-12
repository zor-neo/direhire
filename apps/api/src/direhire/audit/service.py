from sqlalchemy import select
from sqlalchemy.orm import Session

from direhire.models import AccountActivity, AuditEvent


class ActivityService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(self, user_id: str, activity_type: str) -> AccountActivity:
        activity = AccountActivity(user_id=user_id, activity_type=activity_type)
        self.session.add(activity)
        return activity

    def list_for_owner(self, user_id: str, *, limit: int = 50) -> list[AccountActivity]:
        statement = (
            select(AccountActivity)
            .where(AccountActivity.user_id == user_id)
            .order_by(AccountActivity.created_at.desc())
            .limit(min(limit, 100))
        )
        return list(self.session.scalars(statement))


class AuditService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        actor_user_id: str | None,
        actor_role: str,
        action: str,
        target_type: str,
        target_id: str | None,
        result: str,
        correlation_id: str,
        change_metadata: dict[str, object] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action=action,
            target_type=target_type,
            target_id=target_id,
            result=result,
            correlation_id=correlation_id,
            change_metadata=change_metadata or {},
        )
        self.session.add(event)
        return event
