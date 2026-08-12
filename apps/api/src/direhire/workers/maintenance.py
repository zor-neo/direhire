import boto3

from direhire.config import get_settings
from direhire.db import SessionLocal
from direhire.events.outbox import OutboxDispatcher
from direhire.events.sqs import SqsPublisher
from direhire.scheduling.service import ScheduleService


def lambda_handler(event: dict[str, object], context: object) -> dict[str, int]:
    del event, context
    settings = get_settings()
    with SessionLocal() as session:
        scheduled = ScheduleService(session).enqueue_due()
        publisher = SqsPublisher(boto3.client("sqs"), settings.queue_routes)
        published = OutboxDispatcher(session, publisher).dispatch_batch(limit=100)
    return {"scheduled_runs": scheduled, "published_events": published}
