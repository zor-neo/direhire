import logging
from collections.abc import Callable

from direhire.config import get_settings
from direhire.db import SessionLocal
from direhire.events.outbox import EventEnvelope
from direhire.notifications.providers import TelegramSender, WhatsAppSender
from direhire.notifications.service import NotificationDeliveryService, NotificationSender
from direhire.workers.analysis import SsmSecretProvider

logger = logging.getLogger("direhire.workers.notifications")
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
            if (
                envelope.event_type != "notification.digest.requested"
                or envelope.schema_version != 1
            ):
                raise ValueError("unsupported event contract")
            logger.info(
                "Processing notification event id=%s delivery_id=%s",
                event_id,
                envelope.payload.get("delivery_id"),
            )
            processor(envelope)
            logger.info("Completed notification event id=%s", event_id)
        except Exception:
            logger.exception(
                "Failed processing notification SQS record message_id=%s event_id=%s",
                message_id,
                event_id,
            )
            if message_id:
                failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}


def process_notification(envelope: EventEnvelope) -> None:
    delivery_id = envelope.payload.get("delivery_id")
    if not isinstance(delivery_id, str):
        raise ValueError("delivery_id is required")
    settings = get_settings()
    secrets = SsmSecretProvider()
    senders: dict[str, NotificationSender] = {}
    if settings.telegram_enabled:
        senders["TELEGRAM"] = TelegramSender(secrets.get(settings.telegram_token_parameter))
    if settings.whatsapp_enabled:
        senders["WHATSAPP"] = WhatsAppSender(
            secrets.get(settings.whatsapp_token_parameter),
            secrets.get(settings.whatsapp_phone_id_parameter),
            settings.whatsapp_graph_version,
        )
    with SessionLocal() as session:
        NotificationDeliveryService(session, senders).dispatch(delivery_id)


def lambda_handler(event: dict[str, object], context: object) -> dict[str, object]:
    del context
    return handle_sqs_batch(event, process_notification)
