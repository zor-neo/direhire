from typing import Protocol

from direhire.errors import AppError
from direhire.events.outbox import EventEnvelope


class SqsClient(Protocol):
    def send_message(self, **kwargs: object) -> dict[str, object]: ...


class SqsPublisher:
    def __init__(self, client: SqsClient, queue_urls: dict[str, str]) -> None:
        self.client = client
        self.queue_urls = queue_urls

    def publish(self, envelope: EventEnvelope) -> None:
        queue_url = self.queue_urls.get(envelope.event_type)
        if not queue_url:
            raise AppError(
                "QUEUE_ROUTE_MISSING",
                "The background operation is temporarily unavailable.",
                503,
                retryable=True,
            )
        self.client.send_message(
            QueueUrl=queue_url,
            MessageBody=envelope.model_dump_json(),
            MessageAttributes={
                "event_type": {"DataType": "String", "StringValue": envelope.event_type},
                "correlation_id": {
                    "DataType": "String",
                    "StringValue": envelope.correlation_id,
                },
            },
        )
