from pathlib import Path

import pytest
from direhire.errors import AppError
from direhire.sources.adapters.ashby import AshbyAdapter
from direhire.sources.adapters.greenhouse import GreenhouseAdapter
from direhire.sources.adapters.lever import LeverAdapter
from direhire.sources.adapters.personio import PersonioAdapter
from direhire.sources.adapters.pinpoint import PinpointAdapter
from direhire.sources.adapters.recruitee import RecruiteeAdapter

CASES = [
    (
        GreenhouseAdapter(),
        "greenhouse.json",
        "https://boards-api.greenhouse.io/v1/boards/northstar/jobs?content=true",
        "Platform Engineer",
        "Singapore",
    ),
    (
        LeverAdapter(),
        "lever.json",
        "https://api.lever.co/v0/postings/orbit?mode=json",
        "Data Engineer",
        "Bangkok, Thailand",
    ),
    (
        AshbyAdapter(),
        "ashby.json",
        "https://api.ashbyhq.com/posting-api/job-board/harbor?includeCompensation=true",
        "Product Engineer",
        "Remote, APAC",
    ),
    (
        RecruiteeAdapter(),
        "recruitee.json",
        "https://acme.recruitee.com/api/offers/",
        "Security Engineer",
        "Kuala Lumpur, Remote",
    ),
    (
        PersonioAdapter(),
        "personio.xml",
        "https://acme.jobs.personio.de/xml?language=en",
        "Backend Developer",
        "Ho Chi Minh City",
    ),
    (
        PinpointAdapter(),
        "pinpoint.xml",
        "https://acme.pinpointhq.com/jobs.rss",
        "Frontend Engineer",
        "Manila, Philippines",
    ),
]


@pytest.mark.parametrize(("adapter", "fixture_name", "url", "title", "location"), CASES)
def test_launch_adapter_parses_sanitized_fixture(
    adapter, fixture_name, url, title, location
) -> None:
    content = (Path("tests/fixtures/launch_adapters") / fixture_name).read_text(encoding="utf-8")
    adapter.validate_source(url)
    jobs = adapter.discover_jobs(content, url)
    assert len(jobs) == 1
    assert jobs[0].title == title
    assert jobs[0].location_raw == location
    assert jobs[0].company
    assert jobs[0].description
    assert adapter.health_check(content) is True


@pytest.mark.parametrize(("adapter", "fixture_name", "url", "title", "location"), CASES)
def test_launch_adapter_rejects_unrelated_host(adapter, fixture_name, url, title, location) -> None:
    with pytest.raises(AppError) as error:
        adapter.validate_source("https://example.invalid/jobs")
    assert error.value.code == "SOURCE_URL_INVALID"
