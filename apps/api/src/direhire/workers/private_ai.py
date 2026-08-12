from collections.abc import Callable

from sqlalchemy.orm import Session

from direhire.ai.private_orchestrator import PrivateAiOrchestrator
from direhire.ai.providers import HttpxOpenRouterTransport, OpenRouterPrivateProvider
from direhire.config import Settings, get_settings
from direhire.db import SessionLocal
from direhire.errors import AppError
from direhire.events.outbox import EventEnvelope
from direhire.workers.analysis import SecretProvider, SsmSecretProvider

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
            if envelope.event_type != "private.ai.requested" or envelope.schema_version != 1:
                raise ValueError("unsupported event contract")
            processor(envelope)
        except Exception:
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
