from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from direhire.entitlements.service import (
    ACTIVE_WATCH_LIMIT,
    MANUAL_RUN_COOLDOWN_SECONDS,
    MANUAL_RUN_DAILY_LIMIT,
    EntitlementService,
)
from direhire.errors import AppError, ConflictError, NotFoundError
from direhire.models import JobWatch, JobWatchRun, OutboxEvent, WatchSource, utcnow
from direhire.operations.controls import PlatformControlService
from direhire.watches.repository import WatchRepository
from direhire.watches.schemas import WatchCreate, WatchSourceInput, WatchStatus


class WatchService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = WatchRepository(session)

    def create(self, owner_id: str, data: WatchCreate) -> JobWatch:
        values = data.model_dump(exclude={"sources"})
        watch = JobWatch(owner_id=owner_id, **values)
        watch.sources = [self._source_model(source.model_dump()) for source in data.sources]
        self.session.add(watch)
        self.session.commit()
        return watch

    def list(self, owner_id: str) -> list[JobWatch]:
        return self.repository.list_for_owner(owner_id)

    def get(self, watch_id: str, owner_id: str) -> JobWatch:
        return self._owned_watch(watch_id, owner_id)

    def replace(self, watch_id: str, owner_id: str, data: WatchCreate) -> JobWatch:
        watch = self._owned_watch(watch_id, owner_id)
        if watch.status == WatchStatus.ARCHIVED:
            raise ConflictError("Archived Watches cannot be edited.")
        for key, value in data.model_dump(exclude={"sources"}).items():
            setattr(watch, key, value)
        watch.sources = [self._source_model(source.model_dump()) for source in data.sources]
        watch.updated_at = utcnow()
        self.session.commit()
        return watch

    def import_sources(
        self, watch_id: str, owner_id: str, sources: list[WatchSourceInput]
    ) -> JobWatch:
        watch = self._owned_watch(watch_id, owner_id)
        if watch.status == WatchStatus.ARCHIVED:
            raise ConflictError("Archived Watches cannot be edited.")
        existing = {source.source_key for source in watch.sources}
        for source in sources:
            model = self._source_model(source.model_dump())
            if model.source_key not in existing:
                watch.sources.append(model)
                existing.add(model.source_key)
        if len(watch.sources) > 20:
            raise AppError("SOURCE_LIMIT_EXCEEDED", "A Watch can contain up to 20 sources.", 422)
        watch.updated_at = utcnow()
        self.session.commit()
        return watch

    def activate(self, watch_id: str, owner_id: str, plan: str) -> JobWatch:
        watch = self._owned_watch(watch_id, owner_id)
        if watch.status == WatchStatus.ARCHIVED:
            raise ConflictError("Archived Watches cannot be activated.")
        if watch.status != WatchStatus.ACTIVE:
            EntitlementService(self.session).require_capacity(
                user_id=owner_id,
                plan=plan,
                entitlement_key=ACTIVE_WATCH_LIMIT,
                current_usage=self.repository.count_active(owner_id, excluding_watch_id=watch.id),
            )
        watch.status = WatchStatus.ACTIVE
        self.session.commit()
        return watch

    def pause(self, watch_id: str, owner_id: str) -> JobWatch:
        watch = self._owned_watch(watch_id, owner_id)
        if watch.status != WatchStatus.ACTIVE:
            raise ConflictError("Only an active Watch can be paused.")
        watch.status = WatchStatus.PAUSED
        watch.updated_at = utcnow()
        self.session.commit()
        return watch

    def archive(self, watch_id: str, owner_id: str) -> JobWatch:
        watch = self._owned_watch(watch_id, owner_id)
        if watch.status == WatchStatus.ARCHIVED:
            return watch
        watch.status = WatchStatus.ARCHIVED
        watch.updated_at = utcnow()
        self.session.commit()
        return watch

    def delete(self, watch_id: str, owner_id: str) -> None:
        watch = self._owned_watch(watch_id, owner_id)
        outbox_events = self.session.scalars(
            select(OutboxEvent).where(OutboxEvent.event_type == "watch.discovery.requested")
        )
        for event in outbox_events:
            if event.payload.get("watch_id") == watch.id:
                self.session.delete(event)
        self.session.execute(delete(JobWatchRun).where(JobWatchRun.watch_id == watch.id))
        self.session.delete(watch)
        self.session.commit()

    def request_manual_run(self, watch_id: str, owner_id: str, plan: str) -> JobWatchRun:
        controls = PlatformControlService(self.session)
        controls.require("JOB_DISCOVERY", "Job discovery is temporarily unavailable.")
        controls.require("MANUAL_RUN", "Manual runs are temporarily unavailable.")
        watch = self._owned_watch(watch_id, owner_id)
        if watch.status != WatchStatus.ACTIVE:
            raise ConflictError("Only an active Watch can run.")
        if active := self.repository.active_run(watch_id, owner_id):
            return active
        entitlement_service = EntitlementService(self.session)
        cooldown = entitlement_service.resolve(
            user_id=owner_id,
            plan=plan,
            entitlement_key=MANUAL_RUN_COOLDOWN_SECONDS,
        )
        latest_run = self.repository.latest_manual_run(owner_id)
        now = datetime.now(UTC)
        if cooldown.enabled and latest_run is not None:
            created_at = latest_run.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            if created_at + timedelta(seconds=cooldown.limit_value) > now:
                raise AppError(
                    "RATE_LIMITED",
                    "Please wait before starting another manual run.",
                    429,
                    retryable=True,
                )
        entitlement_service.require_capacity(
            user_id=owner_id,
            plan=plan,
            entitlement_key=MANUAL_RUN_DAILY_LIMIT,
            current_usage=self.repository.count_manual_runs_since(
                owner_id, now - timedelta(days=1)
            ),
        )

        run_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())
        run = JobWatchRun(
            id=run_id,
            watch_id=watch.id,
            owner_id=owner_id,
            trigger="MANUAL",
            correlation_id=correlation_id,
            active_marker=watch.id,
        )
        event = OutboxEvent(
            event_id=f"evt_{uuid.uuid4().hex}",
            event_type="watch.discovery.requested",
            schema_version=1,
            correlation_id=correlation_id,
            payload={"run_id": run_id, "watch_id": watch.id, "owner_id": owner_id},
        )
        self.session.add_all((run, event))
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            concurrent_run = self.repository.active_run(watch_id, owner_id)
            if concurrent_run is None:
                raise
            return concurrent_run
        return run

    def list_runs(self, watch_id: str, owner_id: str) -> list[JobWatchRun]:
        self._owned_watch(watch_id, owner_id)
        return self.repository.list_runs(watch_id, owner_id)

    @staticmethod
    def _source_model(data: dict[str, object]) -> WatchSource:
        adapter_key = str(data["adapter_key"])
        url = data.get("url")
        source_key = f"{adapter_key}:{url}" if url else f"{adapter_key}:platform"
        return WatchSource(source_key=source_key, **data)

    def _owned_watch(self, watch_id: str, owner_id: str) -> JobWatch:
        watch = self.repository.get_for_owner(watch_id, owner_id)
        if watch is None:
            # Deliberately indistinguishable from an absent resource.
            raise NotFoundError()
        return watch
