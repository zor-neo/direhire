import logging
from collections.abc import Callable

from direhire.config import get_settings
from direhire.db import SessionLocal
from direhire.documents.service import TailoredCvDocumentProcessor
from direhire.events.outbox import EventEnvelope
from direhire.files.storage import S3PrivateObjectStorage

logger = logging.getLogger("direhire.workers.documents")
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
            if envelope.event_type != "private.document.requested" or envelope.schema_version != 1:
                raise ValueError("unsupported event contract")
            logger.info(
                "Processing document event id=%s document_id=%s",
                event_id,
                envelope.payload.get("document_id"),
            )
            processor(envelope)
            logger.info("Completed document event id=%s", event_id)
        except Exception:
            logger.exception(
                "Failed processing document SQS record message_id=%s event_id=%s",
                message_id,
                event_id,
            )
            if message_id:
                failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}


def process_document(envelope: EventEnvelope) -> None:
    document_id = envelope.payload.get("document_id")
    if not isinstance(document_id, str):
        raise ValueError("document_id is required")
    with SessionLocal() as session:
        TailoredCvDocumentProcessor(
            session,
            S3PrivateObjectStorage(),
            get_settings(),
        ).process(document_id)


def lambda_handler(event: dict[str, object], context: object) -> dict[str, object]:
    del context
    return handle_sqs_batch(event, process_document)
