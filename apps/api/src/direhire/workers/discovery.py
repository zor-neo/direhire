from collections.abc import Callable

from direhire.config import get_settings
from direhire.db import SessionLocal
from direhire.discovery.service import DiscoveryProcessor
from direhire.events.outbox import EventEnvelope
from direhire.sources.http_fetcher import SafePublicFetcher

MessageProcessor = Callable[[EventEnvelope], None]


def handle_sqs_batch(event: dict[str, object], processor: MessageProcessor) -> dict[str, object]:
    failures: list[dict[str, str]] = []
    records = event.get("Records", [])
    if not isinstance(records, list):
        return {"batchItemFailures": failures}
    for record in records:
        if not isinstance(record, dict):
            continue
        message_id = str(record.get("messageId", ""))
        try:
            envelope = EventEnvelope.model_validate_json(str(record.get("body", "")))
            if envelope.event_type != "watch.discovery.requested" or envelope.schema_version != 1:
                raise ValueError("unsupported event contract")
            processor(envelope)
        except Exception:
            if message_id:
                failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}


def process_discovery(envelope: EventEnvelope) -> None:
    run_id = envelope.payload.get("run_id")
    if not isinstance(run_id, str):
        raise ValueError("run_id is required")
    with SessionLocal() as session:
        DiscoveryProcessor(session, SafePublicFetcher(get_settings())).process(run_id)


def lambda_handler(event: dict[str, object], context: object) -> dict[str, object]:
    del context
    return handle_sqs_batch(event, process_discovery)
