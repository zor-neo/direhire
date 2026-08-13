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
from direhire.sources.contracts import SearchRequest
from direhire.watches.schemas import WatchCreate
from direhire.watches.service import WatchService
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A


def test_jobthai_platform_builds_search_request_and_matches_fixture(
    session_factory: sessionmaker[Session],
) -> None:
    fixture = Path("tests/fixtures/jobthai/search.json").read_text(encoding="utf-8")
    captured_request: SearchRequest | None = None

    def provide_content(source: object, request: SearchRequest | None) -> str:
        nonlocal captured_request
        del source
        captured_request = request
        return fixture

    with session_factory() as database:
        database.add(
            User(
                id=str(USER_A),
                cognito_subject="synthetic-jobthai-user",
                email="jobthai@example.invalid",
            )
        )
        database.commit()
        watch = WatchService(database).create(
            str(USER_A),
            WatchCreate(
                name="Backend",
                target_terms=["Python"],
                required_terms=["PostgreSQL"],
                sources=[{"source_kind": "PLATFORM", "platform_key": "jobthai"}],
            ),
        )
        WatchService(database).activate(watch.id, str(USER_A), "FREE")
        run = WatchService(database).request_manual_run(watch.id, str(USER_A), "FREE")

        completed = DiscoveryProcessor(database, provide_content).process(run.id)

        assert completed.status == "SUCCEEDED"
        assert completed.discovered_count == 2
        assert completed.matched_count == 1
        assert captured_request is not None
        assert captured_request.url == "https://api.jobthai.com/v1/graphql"


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
        completed = DiscoveryProcessor(database, lambda source, request: fixture).process(run.id)

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

        repeated = DiscoveryProcessor(database, lambda source, request: fixture).process(run.id)
        assert repeated.id == completed.id
        assert database.scalar(select(func.count()).select_from(Job)) == 1
        assert database.scalar(select(func.count()).select_from(JobDemandProfile)) == 1
