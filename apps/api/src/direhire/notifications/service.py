import re
import uuid
from collections.abc import Mapping
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from direhire.errors import AppError, NotFoundError
from direhire.models import (
    ExternalNotificationDelivery,
    InAppNotification,
    JobWatchRun,
    NotificationDigest,
    NotificationPreference,
    OutboxEvent,
    utcnow,
)
from direhire.operations.controls import PlatformControlService

TELEGRAM_DESTINATION = re.compile(r"^-?[1-9]\d{4,19}$")
WHATSAPP_DESTINATION = re.compile(r"^\+[1-9]\d{7,14}$")


class NotificationSender(Protocol):
    def send(self, destination: str, text: str) -> str: ...


def validate_destination(channel: str, destination: str | None) -> str | None:
    if channel == "NONE":
        return None
    value = (destination or "").strip()
    valid = (
        TELEGRAM_DESTINATION.fullmatch(value)
        if channel == "TELEGRAM"
        else WHATSAPP_DESTINATION.fullmatch(value)
    )
    if valid is None:
        raise AppError(
            "NOTIFICATION_DESTINATION_INVALID",
            "The notification destination is invalid.",
            422,
        )
    return value


def queue_run_digest(session: Session, run: JobWatchRun, *, watch_name: str) -> None:
    if run.matched_count <= 0:
        return
    existing = session.scalar(select(NotificationDigest).where(NotificationDigest.run_id == run.id))
    if existing is not None:
        return
    digest = NotificationDigest(
        run_id=run.id,
        user_id=run.owner_id,
        matched_count=run.matched_count,
    )
    session.add(digest)
    session.flush()
    plural = "s" if run.matched_count != 1 else ""
    session.add(
        InAppNotification(
            user_id=run.owner_id,
            digest_id=digest.id,
            title=f"{run.matched_count} new job{plural}",
            body=(
                f'Your Watch "{watch_name}" completed with {run.matched_count} '
                f"matching job{plural}."
            ),
        )
    )
    preference = session.get(NotificationPreference, run.owner_id)
    if (
        preference is None
        or not preference.enabled
        or preference.external_channel == "NONE"
        or preference.destination is None
    ):
        return
    delivery = ExternalNotificationDelivery(
        digest_id=digest.id,
        channel=preference.external_channel,
        destination=preference.destination,
    )
    session.add(delivery)
    session.flush()
    session.add(
        OutboxEvent(
            event_id=f"evt_{uuid.uuid4().hex}",
            event_type="notification.digest.requested",
            schema_version=1,
            correlation_id=run.correlation_id,
            payload={"delivery_id": delivery.id, "digest_id": digest.id},
        )
    )


class NotificationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_preference(self, user_id: str) -> dict[str, object]:
        preference = self.session.get(NotificationPreference, user_id)
        if preference is None:
            return {"external_channel": "NONE", "enabled": False, "destination_hint": None}
        return self._preference_read(preference)

    def set_preference(
        self, user_id: str, *, channel: str, destination: str | None, enabled: bool
    ) -> dict[str, object]:
        normalized = validate_destination(channel, destination)
        preference = self.session.get(NotificationPreference, user_id)
        if preference is None:
            preference = NotificationPreference(user_id=user_id)
            self.session.add(preference)
        preference.external_channel = channel
        preference.destination = normalized
        preference.enabled = enabled and channel != "NONE"
        preference.updated_at = utcnow()
        self.session.commit()
        return self._preference_read(preference)

    def list_in_app(self, user_id: str) -> list[InAppNotification]:
        return list(
            self.session.scalars(
                select(InAppNotification)
                .where(InAppNotification.user_id == user_id)
                .order_by(InAppNotification.created_at.desc())
            )
        )

    def mark_read(self, notification_id: str, user_id: str) -> InAppNotification:
        notification = self.session.scalar(
            select(InAppNotification).where(
                InAppNotification.id == notification_id,
                InAppNotification.user_id == user_id,
            )
        )
        if notification is None:
            raise NotFoundError()
        if notification.read_at is None:
            notification.read_at = utcnow()
            self.session.commit()
        return notification

    @staticmethod
    def _preference_read(preference: NotificationPreference) -> dict[str, object]:
        destination = preference.destination
        hint = None if destination is None else f"***{destination[-4:]}"
        return {
            "external_channel": preference.external_channel,
            "enabled": preference.enabled,
            "destination_hint": hint,
        }


class NotificationDeliveryService:
    def __init__(self, session: Session, senders: Mapping[str, NotificationSender]) -> None:
        self.session = session
        self.senders = senders

    def dispatch(self, delivery_id: str) -> ExternalNotificationDelivery:
        delivery = self.session.get(ExternalNotificationDelivery, delivery_id)
        if delivery is None:
            raise AppError("DELIVERY_NOT_FOUND", "The delivery was not found.", 404)
        if delivery.status == "SENT" or delivery.attempts >= 5:
            return delivery
        digest = self.session.get(NotificationDigest, delivery.digest_id)
        if digest is None:
            raise AppError("DELIVERY_CANCELLED", "The digest no longer exists.", 409)
        PlatformControlService(self.session).require(
            delivery.channel,
            "The selected notification channel is temporarily unavailable.",
        )
        sender = self.senders.get(delivery.channel)
        if sender is None:
            delivery.status = "FAILED"
            delivery.error_code = "NOTIFICATION_CHANNEL_UNAVAILABLE"
            delivery.attempts += 1
            self.session.commit()
            raise AppError(
                "NOTIFICATION_CHANNEL_UNAVAILABLE",
                "The selected notification channel is unavailable.",
                503,
                retryable=True,
            )
        plural = "s" if digest.matched_count != 1 else ""
        text = (
            f"DireHire found {digest.matched_count} matching job{plural}. "
            "Open your Job Inbox to review them."
        )
        delivery.attempts += 1
        try:
            delivery.provider_message_id = sender.send(delivery.destination, text)
        except Exception as exc:
            delivery.status = "FAILED"
            delivery.error_code = "NOTIFICATION_PROVIDER_FAILED"
            self.session.commit()
            raise AppError(
                "NOTIFICATION_PROVIDER_FAILED",
                "The selected notification channel failed.",
                503,
                retryable=True,
            ) from exc
        delivery.status = "SENT"
        delivery.error_code = None
        delivery.completed_at = utcnow()
        self.session.commit()
        return delivery
