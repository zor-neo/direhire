from pathlib import Path

from direhire.discovery.service import DiscoveryProcessor
from direhire.models import (
    Job,
    JobDemandProfile,
    JobVersion,
    OutboxEvent,
    SourceFetch,
    User,
    UserJob,
    WatchMatch,
)
from direhire.watches.schemas import WatchCreate
from direhire.watches.service import WatchService
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A


def test_discovery_creates_canonical_job_and_preserves_partial_success(
    session_factory: sessionmaker[Session],
) -> None:
    fixture = Path("tests/fixtures/synthetic_board/jobs.html").read_text(encoding="utf-8")
    with session_factory() as database:
        database.add(
            User(
                id=str(USER_A),
                cognito_subject="synthetic-discovery-user",
                email="discovery@example.invalid",
            )
        )
        database.commit()
        watch = WatchService(database).create(
            str(USER_A),
            WatchCreate(
                name="Backend",
                target_terms=["Python"],
                required_terms=["PostgreSQL"],
                sources=[
                    {"source_kind": "PLATFORM", "adapter_key": "synthetic_board"},
                    {"source_kind": "PLATFORM", "adapter_key": "unavailable_adapter"},
                ],
            ),
        )
        WatchService(database).activate(watch.id, str(USER_A), "FREE")
        run = WatchService(database).request_manual_run(watch.id, str(USER_A), "FREE")
        completed = DiscoveryProcessor(database, lambda source: fixture).process(run.id)

        assert completed.status == "SUCCEEDED"
        assert completed.outcome == "COMPLETED_WITH_WARNINGS"
        assert completed.sources_succeeded == 1
        assert completed.sources_failed == 1
        assert completed.discovered_count == 1
        assert completed.matched_count == 1
        assert database.scalar(select(func.count()).select_from(Job)) == 1
        assert database.scalar(select(func.count()).select_from(JobVersion)) == 1
        assert database.scalar(select(func.count()).select_from(UserJob)) == 1
        assert database.scalar(select(func.count()).select_from(WatchMatch)) == 1
        assert database.scalar(select(func.count()).select_from(JobDemandProfile)) == 1
        analysis_events = list(
            database.scalars(
                select(OutboxEvent).where(OutboxEvent.event_type == "job.analysis.requested")
            )
        )
        assert len(analysis_events) == 1
        assert analysis_events[0].correlation_id == run.correlation_id
        fetches = list(database.scalars(select(SourceFetch).order_by(SourceFetch.status)))
        assert {fetch.status for fetch in fetches} == {"SUCCEEDED", "PERMANENT_FAILED"}

        repeated = DiscoveryProcessor(database, lambda source: fixture).process(run.id)
        assert repeated.id == completed.id
        assert database.scalar(select(func.count()).select_from(Job)) == 1
        assert database.scalar(select(func.count()).select_from(JobDemandProfile)) == 1
