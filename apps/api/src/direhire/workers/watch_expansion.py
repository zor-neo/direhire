from direhire.config import get_settings
from direhire.db import SessionLocal
from direhire.errors import AppError
from direhire.events.outbox import EventEnvelope
from direhire.operations.controls import PlatformControlService
from direhire.watches.expansion_orchestrator import WatchExpansionOrchestrator
from direhire.workers.analysis import SsmSecretProvider
from direhire.workers.private_ai import build_provider


def process_watch_expansion(envelope: EventEnvelope) -> None:
    settings = get_settings()
    if not settings.ai_enabled:
        raise AppError("AI_DISABLED", "Search improvement is temporarily unavailable.", 503)
    watch_id = envelope.payload.get("watch_id")
    input_hash = envelope.payload.get("input_hash")
    if not isinstance(watch_id, str) or not isinstance(input_hash, str):
        raise ValueError("watch_id and input_hash are required")
    secrets = SsmSecretProvider()
    with SessionLocal() as session:
        PlatformControlService(session).require(
            "PRIVATE_AI", "Search improvement is temporarily unavailable."
        )
        provider = build_provider(settings, secrets, session)
        WatchExpansionOrchestrator(session, provider).process(
            watch_id,
            input_hash,
            correlation_id=envelope.correlation_id,
        )
