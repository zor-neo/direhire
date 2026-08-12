from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from direhire.models import AiOperation, JobWatchRun, OutboxEvent, SharedSourceFetch


class OperationsService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def summary(self) -> dict[str, object]:
        ai_window = datetime.now(UTC) - timedelta(days=30)
        return {
            "unpublished_outbox": self._count(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
            ),
            "failed_outbox_publications": self._count(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.last_error_code.is_not(None))
            ),
            "active_watch_runs": self._count(
                select(func.count())
                .select_from(JobWatchRun)
                .where(JobWatchRun.status.in_(["QUEUED", "RUNNING"]))
            ),
            "active_ai_operations": self._count(
                select(func.count())
                .select_from(AiOperation)
                .where(AiOperation.status.in_(["QUEUED", "RUNNING", "RETRYABLE_FAILED"]))
            ),
            "active_shared_fetches": self._count(
                select(func.count())
                .select_from(SharedSourceFetch)
                .where(SharedSourceFetch.status == "RUNNING")
            ),
            "ai_tokens_30d": self._sum(
                select(func.sum(AiOperation.total_tokens)).where(
                    AiOperation.created_at >= ai_window
                )
            ),
            "ai_cost_microusd_30d": self._sum(
                select(func.sum(AiOperation.estimated_cost_microusd)).where(
                    AiOperation.created_at >= ai_window
                )
            ),
            "ai_cache_hits_30d": self._count(
                select(func.count())
                .select_from(AiOperation)
                .where(
                    AiOperation.created_at >= ai_window,
                    AiOperation.cache_hit.is_(True),
                )
            ),
        }

    def stuck(self, *, now: datetime | None = None) -> list[dict[str, object]]:
        current = now or datetime.now(UTC)
        outbox_cutoff = current - timedelta(minutes=5)
        workflow_cutoff = current - timedelta(minutes=15)
        items: list[dict[str, object]] = []
        for event in self.session.scalars(
            select(OutboxEvent).where(
                OutboxEvent.published_at.is_(None),
                OutboxEvent.occurred_at < outbox_cutoff,
            )
        ):
            items.append(
                {
                    "kind": "OUTBOX",
                    "id": event.event_id,
                    "status": "UNPUBLISHED",
                    "event_type": event.event_type,
                    "correlation_id": event.correlation_id,
                    "error_code": event.last_error_code,
                    "created_at": event.occurred_at,
                }
            )
        for run in self.session.scalars(
            select(JobWatchRun).where(
                JobWatchRun.status.in_(["QUEUED", "RUNNING"]),
                JobWatchRun.created_at < workflow_cutoff,
            )
        ):
            items.append(
                {
                    "kind": "WATCH_RUN",
                    "id": run.id,
                    "status": run.status,
                    "event_type": None,
                    "correlation_id": run.correlation_id,
                    "error_code": None,
                    "created_at": run.created_at,
                }
            )
        for operation in self.session.scalars(
            select(AiOperation).where(
                AiOperation.status.in_(["QUEUED", "RUNNING", "RETRYABLE_FAILED"]),
                AiOperation.created_at < workflow_cutoff,
            )
        ):
            items.append(
                {
                    "kind": "AI_OPERATION",
                    "id": operation.id,
                    "status": operation.status,
                    "event_type": operation.task,
                    "correlation_id": operation.correlation_id,
                    "error_code": operation.error_code,
                    "created_at": operation.created_at,
                }
            )
        return sorted(items, key=lambda item: str(item["created_at"]))

    def _count(self, statement: object) -> int:
        return int(self.session.scalar(statement) or 0)  # type: ignore[arg-type]

    def _sum(self, statement: object) -> int:
        return int(self.session.scalar(statement) or 0)  # type: ignore[arg-type]
