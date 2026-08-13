import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from direhire.ai.private_orchestrator import PrivateAiOrchestrator
from direhire.ai.providers import HttpxOpenRouterTransport, OpenRouterPrivateProvider
from direhire.config import Settings, get_settings
from direhire.db import SessionLocal
from direhire.errors import AppError
from direhire.events.outbox import EventEnvelope
from direhire.workers.analysis import SecretProvider, SsmSecretProvider

logger = logging.getLogger("direhire.workers.private_ai")
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
            if envelope.event_type != "private.ai.requested" or envelope.schema_version != 1:
                raise ValueError("unsupported event contract")
            logger.info(
                "Processing private AI event id=%s artifact_id=%s",
                event_id,
                envelope.payload.get("artifact_id"),
            )
            processor(envelope)
            logger.info("Completed private AI event id=%s", event_id)
        except Exception:
            logger.exception(
                "Failed processing private AI SQS record message_id=%s event_id=%s",
                message_id,
                event_id,
            )
            if message_id:
                failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}


def build_provider(
    settings: Settings, secrets: SecretProvider, session: Session
) -> OpenRouterPrivateProvider:
    return OpenRouterPrivateProvider(
        session,
        api_key=secrets.get(settings.openrouter_private_parameter),
        approved_providers=settings.openrouter_private_providers,
        transport=HttpxOpenRouterTransport(),
    )


def process_private_ai(envelope: EventEnvelope) -> None:
    settings = get_settings()
    if not settings.ai_enabled:
        raise AppError("AI_DISABLED", "Private AI is temporarily unavailable.", 503)
    artifact_id = envelope.payload.get("artifact_id")
    if not isinstance(artifact_id, str):
        raise ValueError("artifact_id is required")
    secrets = SsmSecretProvider()
    with SessionLocal() as session:
        provider = build_provider(settings, secrets, session)
        PrivateAiOrchestrator(session, provider).process(
            artifact_id, correlation_id=envelope.correlation_id
        )


def lambda_handler(event: dict[str, object], context: object) -> dict[str, object]:
    del context
    return handle_sqs_batch(event, process_private_ai)
