import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from direhire.errors import AppError
from direhire.models import JobWatch, JobWatchRun, OutboxEvent, User, UserSchedule, utcnow
from direhire.operations.controls import PlatformControlService


class ScheduleService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def set_schedule(
        self, user_id: str, timezone_name: str, local_time: time, enabled: bool
    ) -> UserSchedule:
        zone = self._zone(timezone_name)
        schedule = self.session.get(UserSchedule, user_id)
        if schedule is None:
            schedule = UserSchedule(user_id=user_id)
            self.session.add(schedule)
        schedule.timezone = timezone_name
        schedule.local_time = local_time
        schedule.enabled = enabled
        schedule.next_run_at = self._next_occurrence(zone, local_time, datetime.now(UTC))
        schedule.updated_at = utcnow()
        self.session.commit()
        return schedule

    def get(self, user_id: str) -> UserSchedule | None:
        return self.session.get(UserSchedule, user_id)

    def enqueue_due(self, now: datetime | None = None) -> int:
        if not PlatformControlService(self.session).enabled("JOB_DISCOVERY"):
            return 0
        current_time = now or datetime.now(UTC)
        schedules = list(
            self.session.scalars(
                select(UserSchedule).where(
                    UserSchedule.enabled.is_(True), UserSchedule.next_run_at <= current_time
                )
            )
        )
        created = 0
        for schedule in schedules:
            user = self.session.get(User, schedule.user_id)
            if user is None or user.account_status != "ACTIVE":
                schedule.enabled = False
                self.session.commit()
                continue
            zone = self._zone(schedule.timezone)
            schedule_day = current_time.astimezone(zone).date().isoformat()
            watches = self.session.scalars(
                select(JobWatch).where(JobWatch.owner_id == user.id, JobWatch.status == "ACTIVE")
            )
            for watch in watches:
                if self._enqueue_watch(watch, schedule_day):
                    created += 1
            schedule.next_run_at = self._next_occurrence(
                zone, schedule.local_time, current_time + timedelta(seconds=1)
            )
            self.session.commit()
        return created

    def _enqueue_watch(self, watch: JobWatch, schedule_day: str) -> bool:
        run_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())
        run = JobWatchRun(
            id=run_id,
            watch_id=watch.id,
            owner_id=watch.owner_id,
            trigger="SCHEDULED",
            schedule_date=schedule_day,
            correlation_id=correlation_id,
            active_marker=watch.id,
        )
        try:
            with self.session.begin_nested():
                self.session.add_all(
                    (
                        run,
                        OutboxEvent(
                            event_id=f"evt_{uuid.uuid4().hex}",
                            event_type="watch.discovery.requested",
                            schema_version=1,
                            correlation_id=correlation_id,
                            payload={
                                "run_id": run_id,
                                "watch_id": watch.id,
                                "owner_id": watch.owner_id,
                            },
                        ),
                    )
                )
                self.session.flush()
        except IntegrityError:
            return False
        return True

    @staticmethod
    def _zone(name: str) -> ZoneInfo:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError as exc:
            raise AppError("TIMEZONE_INVALID", "Choose a valid IANA timezone.", 422) from exc

    @staticmethod
    def _next_occurrence(zone: ZoneInfo, local_time: time, after: datetime) -> datetime:
        local_after = after.astimezone(zone)
        candidate = datetime.combine(local_after.date(), local_time, tzinfo=zone)
        if candidate <= local_after:
            candidate = datetime.combine(
                date.fromordinal(local_after.date().toordinal() + 1), local_time, tzinfo=zone
            )
        return candidate.astimezone(UTC)
