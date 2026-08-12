from datetime import datetime
from typing import Protocol

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from direhire.models import OutboxEvent, utcnow


class EventEnvelope(BaseModel):
    event_id: str
    event_type: str
    schema_version: int
    occurred_at: datetime
    correlation_id: str
    payload: dict[str, object]


class QueuePublisher(Protocol):
    def publish(self, envelope: EventEnvelope) -> None: ...


class OutboxDispatcher:
    def __init__(self, session: Session, publisher: QueuePublisher) -> None:
        self.session = session
        self.publisher = publisher

    def dispatch_batch(self, *, limit: int = 25) -> int:
        events = list(
            self.session.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.id)
                .limit(min(limit, 100))
            )
        )
        published = 0
        for event in events:
            envelope = EventEnvelope.model_validate(event, from_attributes=True)
            event.publish_attempts += 1
            event.last_attempt_at = utcnow()
            try:
                self.publisher.publish(envelope)
            except Exception:
                event.last_error_code = "QUEUE_PUBLISH_FAILED"
                self.session.commit()
                break
            event.published_at = utcnow()
            event.last_error_code = None
            self.session.commit()
            published += 1
        return published
