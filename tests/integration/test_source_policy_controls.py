from pathlib import Path

from direhire.auth import CurrentUser, current_user
from direhire.discovery.service import DiscoveryProcessor
from direhire.main import app
from direhire.models import AuditEvent, SourcePolicy, User
from direhire.sources.policy_service import SourcePolicyService
from direhire.watches.schemas import WatchCreate
from direhire.watches.service import WatchService
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A


def test_source_policy_controls_are_superadmin_only_and_audited(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    payload = {
        "enabled": True,
        "max_concurrency": 2,
        "minimum_delay_ms": 1500,
        "browser_allowed": False,
        "failure_threshold": 2,
        "cooldown_seconds": 120,
    }
    denied = client.put("/api/v1/admin/source-policies/synthetic_board", json=payload)
    assert denied.status_code == 403

    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_A, role="SUPERADMIN")
    changed = client.put("/api/v1/admin/source-policies/synthetic_board", json=payload)
    assert changed.status_code == 200
    assert changed.json()["failure_threshold"] == 2
    paused = client.post(
        "/api/v1/admin/source-policies/synthetic_board/actions", json={"action": "PAUSE"}
    )
    assert paused.status_code == 200
    assert paused.json()["health"] == "TEMPORARILY_PAUSED"

    with session_factory() as database:
        actions = list(database.scalars(select(AuditEvent.action).order_by(AuditEvent.created_at)))
        assert actions == ["SOURCE_POLICY_UPDATED", "SOURCE_PAUSE"]


def test_repeated_source_failures_open_circuit_and_preserve_other_success(
    session_factory: sessionmaker[Session],
) -> None:
    fixture = Path("tests/fixtures/synthetic_board/jobs.html").read_text(encoding="utf-8")
    with session_factory() as database:
        database.add(
            User(
                id=str(USER_A),
                cognito_subject="source-circuit-user",
                email="source-circuit@example.invalid",
            )
        )
        policy = SourcePolicy(
            adapter_key="unavailable_adapter", failure_threshold=1, cooldown_seconds=60
        )
        database.add(policy)
        database.commit()
        watch = WatchService(database).create(
            str(USER_A),
            WatchCreate(
                name="Circuit",
                target_terms=["Python"],
                sources=[
                    {
                        "source_kind": "CUSTOM_URL",
                        "adapter_key": "synthetic_board",
                        "url": "https://synthetic.example.invalid/jobs",
                    },
                    {
                        "source_kind": "CUSTOM_URL",
                        "adapter_key": "unavailable_adapter",
                        "url": "https://unavailable.example.invalid/jobs",
                    },
                ],
            ),
        )
        WatchService(database).activate(watch.id, str(USER_A), "FREE")
        run = WatchService(database).request_manual_run(watch.id, str(USER_A), "FREE")
        result = DiscoveryProcessor(database, lambda source, request: fixture).process(run.id)

        database.refresh(policy)
        assert result.outcome == "COMPLETED_WITH_WARNINGS"
        assert policy.health == "TEMPORARILY_PAUSED"
        assert policy.cooldown_until is not None
        assert SourcePolicyService(database).unavailable_code(policy.adapter_key) == "SOURCE_PAUSED"
