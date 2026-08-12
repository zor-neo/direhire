from pathlib import Path

import pytest
from direhire.discovery.service import DiscoveryProcessor
from direhire.errors import AppError
from direhire.models import (
    ExternalNotificationDelivery,
    InAppNotification,
    NotificationDigest,
    NotificationPreference,
    OutboxEvent,
    User,
)
from direhire.notifications.service import NotificationDeliveryService
from direhire.watches.schemas import WatchCreate
from direhire.watches.service import WatchService
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A


class FakeSender:
    def __init__(self, *, fails: bool = False) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fails = fails

    def send(self, destination: str, text: str) -> str:
        self.calls.append((destination, text))
        if self.fails:
            raise RuntimeError("synthetic provider failure")
        return "provider-message-1"


def test_one_channel_preference_is_owner_scoped_and_destination_is_masked(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    changed = client.put(
        "/api/v1/notifications/preference",
        json={
            "external_channel": "WHATSAPP",
            "destination": "+66812345678",
            "enabled": True,
        },
    )
    assert changed.status_code == 200
    assert changed.json() == {
        "external_channel": "WHATSAPP",
        "enabled": True,
        "destination_hint": "***5678",
    }
    assert "+66812345678" not in changed.text
    invalid = client.put(
        "/api/v1/notifications/preference",
        json={"external_channel": "TELEGRAM", "destination": "not-a-chat", "enabled": True},
    )
    assert invalid.status_code == 422


def test_matching_run_creates_one_in_app_digest_and_one_selected_external_delivery(
    session_factory: sessionmaker[Session],
) -> None:
    fixture = Path("tests/fixtures/synthetic_board/jobs.html").read_text(encoding="utf-8")
    with session_factory() as database:
        database.add(
            User(
                id=str(USER_A),
                cognito_subject="notification-user",
                email="notification@example.invalid",
            )
        )
        database.add(
            NotificationPreference(
                user_id=str(USER_A),
                external_channel="TELEGRAM",
                destination="123456789",
                enabled=True,
            )
        )
        database.commit()
        watch = WatchService(database).create(
            str(USER_A),
            WatchCreate(
                name="Digest Watch",
                target_terms=["Python"],
                required_terms=["PostgreSQL"],
                sources=[{"source_kind": "PLATFORM", "adapter_key": "synthetic_board"}],
            ),
        )
        WatchService(database).activate(watch.id, str(USER_A), "FREE")
        run = WatchService(database).request_manual_run(watch.id, str(USER_A), "FREE")
        processor = DiscoveryProcessor(database, lambda source: fixture)
        processor.process(run.id)
        processor.process(run.id)

        assert database.scalar(select(func.count()).select_from(NotificationDigest)) == 1
        assert database.scalar(select(func.count()).select_from(InAppNotification)) == 1
        assert database.scalar(select(func.count()).select_from(ExternalNotificationDelivery)) == 1
        event = database.scalar(
            select(OutboxEvent).where(OutboxEvent.event_type == "notification.digest.requested")
        )
        assert event is not None
        assert event.correlation_id == run.correlation_id


def test_delivery_is_idempotent_and_never_fails_over_channels(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as database:
        database.add(
            User(
                id=str(USER_A),
                cognito_subject="delivery-user",
                email="delivery@example.invalid",
            )
        )
        watch = WatchService(database).create(
            str(USER_A), WatchCreate(name="Delivery", target_terms=["Python"])
        )
        database.add(
            NotificationPreference(
                user_id=str(USER_A),
                external_channel="TELEGRAM",
                destination="123456789",
                enabled=True,
            )
        )
        database.commit()
        WatchService(database).activate(watch.id, str(USER_A), "FREE")
        run = WatchService(database).request_manual_run(watch.id, str(USER_A), "FREE")
        run.matched_count = 2
        from direhire.notifications.service import queue_run_digest

        queue_run_digest(database, run, watch_name=watch.name)
        database.commit()
        delivery = database.scalar(select(ExternalNotificationDelivery))
        assert delivery is not None
        telegram = FakeSender()
        whatsapp = FakeSender()
        service = NotificationDeliveryService(
            database, {"TELEGRAM": telegram, "WHATSAPP": whatsapp}
        )
        service.dispatch(delivery.id)
        service.dispatch(delivery.id)

        assert len(telegram.calls) == 1
        assert whatsapp.calls == []
        assert delivery.status == "SENT"


def test_failed_selected_channel_stays_failed_without_failover(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as database:
        database.add(
            User(id=str(USER_A), cognito_subject="failed-user", email="failed@example.invalid")
        )
        watch = WatchService(database).create(
            str(USER_A), WatchCreate(name="Failed", target_terms=["Python"])
        )
        database.add(
            NotificationPreference(
                user_id=str(USER_A),
                external_channel="TELEGRAM",
                destination="123456789",
                enabled=True,
            )
        )
        database.commit()
        WatchService(database).activate(watch.id, str(USER_A), "FREE")
        run = WatchService(database).request_manual_run(watch.id, str(USER_A), "FREE")
        run.matched_count = 1
        from direhire.notifications.service import queue_run_digest

        queue_run_digest(database, run, watch_name=watch.name)
        database.commit()
        delivery = database.scalar(select(ExternalNotificationDelivery))
        assert delivery is not None
        telegram = FakeSender(fails=True)
        whatsapp = FakeSender()
        with pytest.raises(AppError):
            NotificationDeliveryService(
                database, {"TELEGRAM": telegram, "WHATSAPP": whatsapp}
            ).dispatch(delivery.id)

        assert delivery.status == "FAILED"
        assert delivery.attempts == 1
        assert whatsapp.calls == []
