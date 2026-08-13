import logging
from collections.abc import Callable

from direhire.analyze.service import PublicAnalyzeJobProcessor
from direhire.config import get_settings
from direhire.db import SessionLocal
from direhire.events.outbox import EventEnvelope
from direhire.sources.http_fetcher import SafePublicFetcher

logger = logging.getLogger("direhire.workers.analyze_job")
logger.setLevel(logging.INFO)

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
        event_id = "unknown"
        try:
            envelope = EventEnvelope.model_validate_json(str(record.get("body", "")))
            event_id = envelope.event_id
            if envelope.event_type != "analyze.job.requested" or envelope.schema_version != 1:
                raise ValueError("unsupported event contract")
            logger.info(
                "Processing analyze_job event id=%s analysis_id=%s",
                event_id,
                envelope.payload.get("analysis_id"),
            )
            processor(envelope)
            logger.info("Completed analyze_job event id=%s", event_id)
        except Exception:
            logger.exception(
                "Failed processing analyze_job SQS record message_id=%s event_id=%s",
                message_id,
                event_id,
            )
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
