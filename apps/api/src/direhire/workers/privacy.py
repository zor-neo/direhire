from collections.abc import Callable

from direhire.config import get_settings
from direhire.db import SessionLocal
from direhire.events.outbox import EventEnvelope
from direhire.files.storage import S3PrivateObjectStorage
from direhire.privacy.service import DeletionProcessor, ExportProcessor

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
            if envelope.schema_version != 1 or envelope.event_type not in {
                "privacy.export.requested",
                "privacy.deletion.requested",
            }:
                raise ValueError("unsupported event contract")
            processor(envelope)
        except Exception:
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
