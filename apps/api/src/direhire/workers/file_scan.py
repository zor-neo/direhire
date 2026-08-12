from collections.abc import Callable

from direhire.config import get_settings
from direhire.db import SessionLocal
from direhire.events.outbox import EventEnvelope
from direhire.files.extraction import SafeCvTextExtractor
from direhire.files.service import FileScanService
from direhire.files.storage import S3PrivateObjectStorage
from direhire.files.validation import ClamAvScanner

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
            if envelope.event_type != "file.scan.requested" or envelope.schema_version != 1:
                raise ValueError("unsupported event contract")
            processor(envelope)
        except Exception:
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
