import logging
from collections.abc import Callable

from direhire.config import get_settings
from direhire.db import SessionLocal
from direhire.events.outbox import EventEnvelope
from direhire.files.extraction import SafeCvTextExtractor
from direhire.files.service import FileScanService
from direhire.files.storage import S3PrivateObjectStorage
from direhire.files.validation import ClamAvScanner

logger = logging.getLogger("direhire.workers.file_scan")
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
            if envelope.event_type != "file.scan.requested" or envelope.schema_version != 1:
                raise ValueError("unsupported event contract")
            logger.info(
                "Processing file_scan event id=%s file_id=%s",
                event_id,
                envelope.payload.get("file_id"),
            )
            processor(envelope)
            logger.info("Completed file_scan event id=%s", event_id)
        except Exception:
            logger.exception(
                "Failed processing file_scan SQS record message_id=%s event_id=%s",
                message_id,
                event_id,
            )
            if message_id:
                failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}


def process_file_scan(envelope: EventEnvelope) -> None:
    file_id = envelope.payload.get("file_id")
    if not isinstance(file_id, str):
        raise ValueError("file_id is required")
    with SessionLocal() as session:
        FileScanService(
            session,
            S3PrivateObjectStorage(),
            ClamAvScanner(),
            get_settings(),
            SafeCvTextExtractor(),
        ).process(file_id)


def lambda_handler(event: dict[str, object], context: object) -> dict[str, object]:
    del context
    return handle_sqs_batch(event, process_file_scan)
