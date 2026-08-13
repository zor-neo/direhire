import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from direhire.discovery.service import DiscoveryProcessor
from direhire.models import JobWatchRun, SharedSourceFetch, SourceFetch, User
from direhire.sources.adapters.synthetic_board import SyntheticBoardAdapter
from direhire.sources.coalescing import SharedFetchPending, SourceFetchCoalescer
from direhire.watches.schemas import WatchCreate
from direhire.watches.service import WatchService
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A


def seed_watch(database: Session, name: str) -> object:
    watch = WatchService(database).create(
        str(USER_A),
        WatchCreate(
            name=name,
            target_terms=["Python"],
            required_terms=["PostgreSQL"],
            sources=[
                {
                    "source_kind": "CUSTOM_URL",
                    "adapter_key": "synthetic_board",
                    "url": "https://synthetic.example.invalid/jobs",
                }
            ],
        ),
    )
    WatchService(database).activate(watch.id, str(USER_A), "PREMIUM")
    return watch


def test_recent_public_fetch_is_reused_across_watch_runs(
    session_factory: sessionmaker[Session],
) -> None:
    fixture = Path("tests/fixtures/synthetic_board/jobs.html").read_text(encoding="utf-8")
    calls = 0

    def content_provider(source: object, request: object) -> str:
        nonlocal calls
        del source, request
        calls += 1
        return fixture

    with session_factory() as database:
        database.add(
            User(
                id=str(USER_A),
                cognito_subject="coalescing-user",
                email="coalescing@example.invalid",
                plan="PREMIUM",
            )
        )
        database.commit()
        first = seed_watch(database, "First")
        second = seed_watch(database, "Second")
        first_run = JobWatchRun(
            watch_id=first.id,
            owner_id=str(USER_A),
            trigger="SCHEDULED",
            status="QUEUED",
            active_marker=first.id,
            correlation_id="f" * 36,
        )
        database.add(first_run)
        database.commit()
        DiscoveryProcessor(database, content_provider).process(first_run.id)
        second_run = JobWatchRun(
            watch_id=second.id,
            owner_id=str(USER_A),
            trigger="SCHEDULED",
            status="QUEUED",
            active_marker=second.id,
            correlation_id="s" * 36,
        )
        database.add(second_run)
        database.commit()
        completed = DiscoveryProcessor(database, content_provider).process(second_run.id)

        assert completed.status == "SUCCEEDED"
        assert calls == 1
        assert database.scalar(select(func.count()).select_from(SharedSourceFetch)) == 1


def test_live_shared_fetch_keeps_run_retryable_until_result_is_available(
    session_factory: sessionmaker[Session],
) -> None:
    fixture = Path("tests/fixtures/synthetic_board/jobs.html").read_text(encoding="utf-8")
    with session_factory() as database:
        database.add(
            User(
                id=str(USER_A),
                cognito_subject="pending-fetch-user",
                email="pending@example.invalid",
                plan="PREMIUM",
            )
        )
        database.commit()
        watch = seed_watch(database, "Pending")
        run = WatchService(database).request_manual_run(watch.id, str(USER_A), "PREMIUM")
        normalized_source = "https://synthetic.example.invalid/jobs"
        key = hashlib.sha256(f"synthetic_board|GET|{normalized_source}|".encode()).hexdigest()
        shared = SharedSourceFetch(
            fetch_key=key,
            adapter_key="synthetic_board",
            normalized_source=normalized_source,
            status="RUNNING",
            owner_run_id="another-run",
            lease_expires_at=datetime.now(UTC) + timedelta(minutes=1),
        )
        database.add(shared)
        database.commit()

        with pytest.raises(SharedFetchPending):
            DiscoveryProcessor(database, lambda source, request: fixture).process(run.id)
        database.refresh(run)
        assert run.status == "QUEUED"
        assert run.sources_failed == 0
        assert database.scalar(select(func.count()).select_from(SourceFetch)) == 0

        shared.status = "SUCCEEDED"
        shared.owner_run_id = None
        shared.lease_expires_at = None
        shared.result_expires_at = datetime.now(UTC) + timedelta(minutes=5)
        shared.results = SourceFetchCoalescer._serialize(
            SyntheticBoardAdapter().discover_jobs(fixture)
        )
        database.commit()
        completed = DiscoveryProcessor(
            database,
            lambda source, request: (_ for _ in ()).throw(AssertionError("should reuse cache")),
        ).process(run.id)
        assert completed.status == "SUCCEEDED"
