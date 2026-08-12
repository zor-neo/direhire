from datetime import UTC, datetime, time

from direhire.models import JobWatch, JobWatchRun, OutboxEvent, User
from direhire.scheduling.service import ScheduleService
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A


def test_daily_schedule_enqueues_all_active_watches_once(
    session_factory: sessionmaker[Session],
) -> None:
    now = datetime(2026, 8, 12, 2, 0, tzinfo=UTC)
    with session_factory() as database:
        database.add(
            User(
                id=str(USER_A),
                cognito_subject="schedule-user",
                email="schedule@example.invalid",
            )
        )
        database.add_all(
            (
                JobWatch(owner_id=str(USER_A), name="One", status="ACTIVE", target_terms=["A"]),
                JobWatch(owner_id=str(USER_A), name="Two", status="ACTIVE", target_terms=["B"]),
                JobWatch(owner_id=str(USER_A), name="Draft", status="DRAFT", target_terms=["C"]),
            )
        )
        database.commit()
        service = ScheduleService(database)
        schedule = service.set_schedule(str(USER_A), "Asia/Bangkok", time(9, 0), True)
        schedule.next_run_at = now
        database.commit()

        assert service.enqueue_due(now) == 2
        assert service.enqueue_due(now) == 0
        assert database.scalar(select(func.count()).select_from(JobWatchRun)) == 2
        assert database.scalar(select(func.count()).select_from(OutboxEvent)) == 2
        dates = set(database.scalars(select(JobWatchRun.schedule_date)))
        assert dates == {"2026-08-12"}
