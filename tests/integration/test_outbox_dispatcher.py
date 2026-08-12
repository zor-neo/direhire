from datetime import UTC, datetime

from direhire.events.outbox import EventEnvelope, OutboxDispatcher
from direhire.models import OutboxEvent
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker


class RecordingPublisher:
    def __init__(self, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.events: list[EventEnvelope] = []

    def publish(self, envelope: EventEnvelope) -> None:
        if envelope.event_id == self.fail_on:
            raise RuntimeError("synthetic queue failure")
        self.events.append(envelope)


def test_dispatch_marks_only_successfully_published_events(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as database:
        database.add_all((event("evt_" + "a" * 32), event("evt_" + "b" * 32)))
        database.commit()
        publisher = RecordingPublisher(fail_on="evt_" + "b" * 32)
        count = OutboxDispatcher(database, publisher).dispatch_batch()
        assert count == 1
        stored = list(database.scalars(select(OutboxEvent).order_by(OutboxEvent.id)))
        assert stored[0].published_at is not None
        assert stored[1].published_at is None
        assert stored[0].publish_attempts == 1
        assert stored[0].last_error_code is None
        assert stored[1].publish_attempts == 1
        assert stored[1].last_error_code == "QUEUE_PUBLISH_FAILED"
        assert stored[1].last_attempt_at is not None
        assert publisher.events[0].event_id == "evt_" + "a" * 32


def event(event_id: str) -> OutboxEvent:
    return OutboxEvent(
        event_id=event_id,
        event_type="watch.discovery.requested",
        schema_version=1,
        occurred_at=datetime(2026, 8, 12, tzinfo=UTC),
        correlation_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        payload={"run_id": "run", "watch_id": "watch", "owner_id": "owner"},
    )
