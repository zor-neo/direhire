from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from direhire.models import JobWatch, JobWatchRun


class WatchRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_owner(self, owner_id: str) -> list[JobWatch]:
        statement = (
            select(JobWatch).where(JobWatch.owner_id == owner_id).order_by(JobWatch.created_at)
        )
        return list(self.session.scalars(statement))

    def get_for_owner(self, watch_id: str, owner_id: str) -> JobWatch | None:
        statement = select(JobWatch).where(JobWatch.id == watch_id, JobWatch.owner_id == owner_id)
        return self.session.scalar(statement)

    def active_run(self, watch_id: str, owner_id: str) -> JobWatchRun | None:
        statement = select(JobWatchRun).where(
            JobWatchRun.watch_id == watch_id,
            JobWatchRun.owner_id == owner_id,
            JobWatchRun.status.in_(("QUEUED", "RUNNING")),
        )
        return self.session.scalar(statement)

    def count_active(self, owner_id: str, *, excluding_watch_id: str | None = None) -> int:
        statement = (
            select(func.count())
            .select_from(JobWatch)
            .where(
                JobWatch.owner_id == owner_id,
                JobWatch.status == "ACTIVE",
            )
        )
        if excluding_watch_id is not None:
            statement = statement.where(JobWatch.id != excluding_watch_id)
        return int(self.session.scalar(statement) or 0)

    def count_manual_runs_since(self, owner_id: str, since: datetime) -> int:
        statement = (
            select(func.count())
            .select_from(JobWatchRun)
            .where(
                JobWatchRun.owner_id == owner_id,
                JobWatchRun.trigger == "MANUAL",
                JobWatchRun.created_at >= since,
                JobWatchRun.status.not_in(("CANCELLED", "PERMANENT_FAILED")),
            )
        )
        return int(self.session.scalar(statement) or 0)

    def latest_manual_run(self, owner_id: str) -> JobWatchRun | None:
        statement = (
            select(JobWatchRun)
            .where(
                JobWatchRun.owner_id == owner_id,
                JobWatchRun.trigger == "MANUAL",
                JobWatchRun.status != "CANCELLED",
            )
            .order_by(JobWatchRun.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def list_runs(self, watch_id: str, owner_id: str, *, limit: int = 50) -> list[JobWatchRun]:
        statement = (
            select(JobWatchRun)
            .where(JobWatchRun.watch_id == watch_id, JobWatchRun.owner_id == owner_id)
            .order_by(JobWatchRun.created_at.desc())
            .limit(min(limit, 100))
        )
        return list(self.session.scalars(statement))
