import os
from collections.abc import Callable

from direhire.events.outbox import EventEnvelope
from direhire.workers.analysis import process_analysis
from direhire.workers.analyze_job import process_analysis as process_analyze_job
from direhire.workers.discovery import process_discovery
from direhire.workers.documents import process_document
from direhire.workers.file_scan import process_file_scan
from direhire.workers.notifications import process_notification
from direhire.workers.privacy import process_privacy_workflow
from direhire.workers.private_ai import process_private_ai
from direhire.workers.watch_expansion import process_watch_expansion

MessageProcessor = Callable[[EventEnvelope], None]

PROCESSORS: dict[str, tuple[str, MessageProcessor]] = {
    "watch.discovery.requested": ("source-discovery", process_discovery),
    "analyze.job.requested": ("source-discovery", process_analyze_job),
    "job.analysis.requested": ("ai-analysis", process_analysis),
    "private.ai.requested": ("interactive-ai", process_private_ai),
    "watch.query-expansion.requested": ("interactive-ai", process_watch_expansion),
    "notification.digest.requested": ("notification", process_notification),
    "private.document.requested": ("documents", process_document),
    "file.scan.requested": ("documents", process_file_scan),
    "privacy.export.requested": ("maintenance", process_privacy_workflow),
    "privacy.deletion.requested": ("maintenance", process_privacy_workflow),
}


def handle_sqs_batch(event: dict[str, object], *, workload: str | None = None) -> dict[str, object]:
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
            route = PROCESSORS.get(envelope.event_type)
            if route is None or envelope.schema_version != 1:
                raise ValueError("unsupported event contract")
            expected_workload, processor = route
            if workload and workload != expected_workload:
                raise ValueError("event delivered to the wrong workload queue")
            processor(envelope)
        except Exception:
            if message_id:
                failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}


def lambda_handler(event: dict[str, object], context: object) -> dict[str, object]:
    del context
    return handle_sqs_batch(event, workload=os.getenv("DIREHIRE_WORKLOAD"))
