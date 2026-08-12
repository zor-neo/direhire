import json

from direhire.events.outbox import EventEnvelope
from direhire.events.sqs import SqsPublisher
from direhire.workers.discovery import handle_sqs_batch


class FakeSqs:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    def send_message(self, **kwargs: object) -> dict[str, object]:
        self.messages.append(kwargs)
        return {"MessageId": "message-1"}


def test_sqs_publisher_routes_versioned_envelope_with_metadata() -> None:
    client = FakeSqs()
    publisher = SqsPublisher(
        client, {"watch.discovery.requested": "https://sqs.example.invalid/discovery"}
    )
    envelope = EventEnvelope.model_validate(
        {
            "event_id": "evt_" + "a" * 32,
            "event_type": "watch.discovery.requested",
            "schema_version": 1,
            "occurred_at": "2026-08-12T00:00:00Z",
            "correlation_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "payload": {"run_id": "run"},
        }
    )
    publisher.publish(envelope)
    body = json.loads(str(client.messages[0]["MessageBody"]))
    assert body["event_id"] == envelope.event_id
    assert (
        client.messages[0]["MessageAttributes"]["correlation_id"]["StringValue"]
        == envelope.correlation_id
    )


def test_batch_handler_returns_only_failed_message_ids() -> None:
    good = {
        "event_id": "evt_" + "a" * 32,
        "event_type": "watch.discovery.requested",
        "schema_version": 1,
        "occurred_at": "2026-08-12T00:00:00Z",
        "correlation_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "payload": {"run_id": "run"},
    }
    processed: list[str] = []
    result = handle_sqs_batch(
        {
            "Records": [
                {"messageId": "good", "body": json.dumps(good)},
                {"messageId": "bad", "body": "not-json"},
            ]
        },
        lambda envelope: processed.append(envelope.event_id),
    )
    assert processed == [good["event_id"]]
    assert result == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
