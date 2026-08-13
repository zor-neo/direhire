import logging
from collections.abc import Callable

from direhire.config import get_settings
from direhire.db import SessionLocal
from direhire.events.outbox import EventEnvelope
from direhire.files.storage import S3PrivateObjectStorage
from direhire.privacy.service import DeletionProcessor, ExportProcessor

logger = logging.getLogger("direhire.workers.privacy")
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
            if envelope.schema_version != 1 or envelope.event_type not in {
                "privacy.export.requested",
                "privacy.deletion.requested",
            }:
                raise ValueError("unsupported event contract")
            logger.info("Processing privacy event id=%s type=%s", event_id, envelope.event_type)
            processor(envelope)
            logger.info("Completed privacy event id=%s", event_id)
        except Exception:
            logger.exception(
                "Failed processing privacy SQS record message_id=%s event_id=%s",
                message_id,
                event_id,
            )
            if message_id:
                failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}


def process_privacy_workflow(envelope: EventEnvelope) -> None:
    storage = S3PrivateObjectStorage()
    with SessionLocal() as session:
        if envelope.event_type == "privacy.export.requested":
            export_id = envelope.payload.get("export_id")
            if not isinstance(export_id, str):
                raise ValueError("export_id is required")
            ExportProcessor(session, storage, get_settings()).process(export_id)
            return
        workflow_id = envelope.payload.get("workflow_id")
        if not isinstance(workflow_id, str):
            raise ValueError("workflow_id is required")
        DeletionProcessor(session, storage).process(workflow_id)


def lambda_handler(event: dict[str, object], context: object) -> dict[str, object]:
    del context
    return handle_sqs_batch(event, process_privacy_workflow)
