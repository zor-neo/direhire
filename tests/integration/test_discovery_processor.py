from pathlib import Path

from direhire.config import Settings
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


def test_remotive_platform_discovers_matches_with_attributed_source_link(
    session_factory: sessionmaker[Session],
) -> None:
    fixture = Path("tests/fixtures/remotive/jobs.json").read_text(encoding="utf-8")
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
                cognito_subject="synthetic-remotive-user",
                email="remotive@example.invalid",
            )
        )
        database.commit()
        watch = WatchService(database).create(
            str(USER_A),
            WatchCreate(
                name="Remote backend",
                target_terms=["Python"],
                required_terms=["PostgreSQL"],
                sources=[{"source_kind": "PLATFORM", "platform_key": "remotive"}],
            ),
        )
        WatchService(database).activate(watch.id, str(USER_A), "FREE")
        run = WatchService(database).request_manual_run(watch.id, str(USER_A), "FREE")

        completed = DiscoveryProcessor(database, provide_content).process(run.id)

        assert completed.status == "SUCCEEDED"
        assert completed.discovered_count == 2
        assert completed.matched_count == 1
        assert captured_request is not None
        assert captured_request.url == "https://remotive.com/api/remote-jobs"
        assert captured_request.cache_seconds == 6 * 60 * 60
        version = database.scalar(select(JobVersion))
        assert version is not None
        assert version.source_url.startswith("https://remotive.com/remote-jobs/")


def test_workable_careers_url_resolves_and_discovers_full_description(
    session_factory: sessionmaker[Session],
) -> None:
    fixture = Path("tests/fixtures/launch_adapters/workable.json").read_text(encoding="utf-8")
    captured_source: object | None = None

    def provide_content(source: object, request: SearchRequest | None) -> str:
        nonlocal captured_source
        assert request is None
        captured_source = source
        return fixture

    with session_factory() as database:
        database.add(
            User(
                id=str(USER_A),
                cognito_subject="synthetic-workable-user",
                email="workable@example.invalid",
            )
        )
        database.commit()
        watch = WatchService(database).create(
            str(USER_A),
            WatchCreate(
                name="Cambodia reliability",
                target_terms=["Python"],
                required_terms=["PostgreSQL"],
                sources=[
                    {
                        "source_kind": "CUSTOM_URL",
                        "adapter_key": "generic_public",
                        "url": "https://apply.workable.com/northstar/",
                    }
                ],
            ),
        )
        source = watch.sources[0]
        assert source.adapter_key == "workable"
        assert source.url == (
            "https://apply.workable.com/api/v1/widget/accounts/northstar?details=true"
        )
        WatchService(database).activate(watch.id, str(USER_A), "FREE")
        run = WatchService(database).request_manual_run(watch.id, str(USER_A), "FREE")

        completed = DiscoveryProcessor(database, provide_content).process(run.id)

        assert captured_source is not None
        assert completed.status == "SUCCEEDED"
        assert completed.discovered_count == 1
        assert completed.matched_count == 1
        version = database.scalar(select(JobVersion))
        assert version is not None
        assert version.source_url == "https://apply.workable.com/j/SYNTHETIC-SRE-01"


def test_usajobs_platform_discovers_public_federal_job_end_to_end(
    session_factory: sessionmaker[Session], monkeypatch
) -> None:
    settings = Settings(usajobs_enabled=True)
    monkeypatch.setattr("direhire.sources.platforms.get_settings", lambda: settings)
    monkeypatch.setattr("direhire.discovery.service.get_settings", lambda: settings)
    fixture = Path("tests/fixtures/usajobs/search.json").read_text(encoding="utf-8")
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
                cognito_subject="synthetic-usajobs-user",
                email="usajobs@example.invalid",
            )
        )
        database.commit()
        watch = WatchService(database).create(
            str(USER_A),
            WatchCreate(
                name="Federal software",
                target_terms=["Python"],
                required_terms=["PostgreSQL"],
                locations=["Washington, DC"],
                sources=[{"source_kind": "PLATFORM", "platform_key": "usajobs"}],
            ),
        )
        WatchService(database).activate(watch.id, str(USER_A), "FREE")
        run = WatchService(database).request_manual_run(watch.id, str(USER_A), "FREE")

        completed = DiscoveryProcessor(database, provide_content).process(run.id)

        assert completed.status == "SUCCEEDED"
        assert completed.discovered_count == 1
        assert completed.matched_count == 1
        assert captured_request is not None
        assert captured_request.url.startswith("https://data.usajobs.gov/api/search?")
        assert "Authorization-Key" in captured_request.secret_headers
        version = database.scalar(select(JobVersion))
        assert version is not None
        assert version.source_url == "https://www.usajobs.gov/job/81000100"


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
