from collections.abc import Callable

from direhire.analyze.service import PublicAnalyzeJobProcessor
from direhire.config import get_settings
from direhire.db import SessionLocal
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
            if envelope.event_type != "analyze.job.requested" or envelope.schema_version != 1:
                raise ValueError("unsupported event contract")
            processor(envelope)
        except Exception:
            if message_id:
                failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}


def process_analysis(envelope: EventEnvelope) -> None:
    analysis_id = envelope.payload.get("analysis_id")
    if not isinstance(analysis_id, str):
        raise ValueError("analysis_id is required")
    settings = get_settings()
    fetcher = SafePublicFetcher(settings)
    with SessionLocal() as session:
        PublicAnalyzeJobProcessor(session, fetcher.fetch_url).process(
            analysis_id, envelope.correlation_id
        )


def lambda_handler(event: dict[str, object], context: object) -> dict[str, object]:
    del context
    return handle_sqs_batch(event, process_analysis)
