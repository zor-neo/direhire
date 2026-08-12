from collections.abc import Callable
from typing import Protocol

from direhire.ai.orchestrator import AiOrchestrator
from direhire.ai.providers import GeminiCredential, GeminiPoolProvider, HttpxGeminiTransport
from direhire.config import Settings, get_settings
from direhire.db import SessionLocal
from direhire.errors import AppError
from direhire.events.outbox import EventEnvelope

MessageProcessor = Callable[[EventEnvelope], None]


class SecretProvider(Protocol):
    def get(self, parameter_name: str) -> str: ...


class SsmSecretProvider:
    def __init__(self) -> None:
        import boto3  # Available in the Lambda runtime; never imported in routine local tests.

        self.client = boto3.client("ssm")

    def get(self, parameter_name: str) -> str:
        response = self.client.get_parameter(Name=parameter_name, WithDecryption=True)
        return str(response["Parameter"]["Value"])


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
            if envelope.event_type != "job.analysis.requested" or envelope.schema_version != 1:
                raise ValueError("unsupported event contract")
            processor(envelope)
        except Exception:
            if message_id:
                failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}


def build_credentials(settings: Settings, secrets: SecretProvider) -> list[GeminiCredential]:
    return [
        GeminiCredential("project-a", secrets.get(settings.gemini_project_a_parameter)),
        GeminiCredential("project-b", secrets.get(settings.gemini_project_b_parameter)),
        GeminiCredential("project-c", secrets.get(settings.gemini_project_c_parameter)),
    ]


def process_analysis(envelope: EventEnvelope) -> None:
    settings = get_settings()
    if not settings.ai_enabled:
        raise AppError("AI_DISABLED", "Job analysis is temporarily unavailable.", 503)
    profile_id = envelope.payload.get("profile_id")
    if not isinstance(profile_id, str):
        raise ValueError("profile_id is required")
    secrets = SsmSecretProvider()
    with SessionLocal() as session:
        provider = GeminiPoolProvider(
            session,
            build_credentials(settings, secrets),
            HttpxGeminiTransport(),
        )
        AiOrchestrator(session, provider).analyze_public_job(
            profile_id, correlation_id=envelope.correlation_id
        )


def lambda_handler(event: dict[str, object], context: object) -> dict[str, object]:
    del context
    return handle_sqs_batch(event, process_analysis)
