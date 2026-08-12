from collections.abc import Callable

from direhire.config import get_settings
from direhire.db import SessionLocal
from direhire.documents.service import TailoredCvDocumentProcessor
from direhire.events.outbox import EventEnvelope
from direhire.files.storage import S3PrivateObjectStorage

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
            if envelope.event_type != "private.document.requested" or envelope.schema_version != 1:
                raise ValueError("unsupported event contract")
            processor(envelope)
        except Exception:
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
