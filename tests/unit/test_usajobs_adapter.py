from pathlib import Path

import pytest
from direhire.config import Settings
from direhire.errors import AppError
from direhire.sources.adapters.usajobs import USAJobsAdapter
from direhire.sources.contracts import SearchQuery


def test_usajobs_builds_bounded_official_api_request() -> None:
    adapter = USAJobsAdapter(Settings(usajobs_enabled=True))

    request = adapter.build_search_request(
        "usajobs",
        SearchQuery(
            keywords=("Python", "PostgreSQL"),
            location="Washington, DC",
            experience_level="MID",
            posting_age_days=14,
        ),
    )

    assert request.method == "GET"
    assert request.url.startswith("https://data.usajobs.gov/api/search?")
    assert "Keyword=Python+PostgreSQL" in request.url
    assert "LocationName=Washington%2C+DC" in request.url
    assert "WhoMayApply=Public" in request.url
    assert "Fields=Full" in request.url
    assert "ResultsPerPage=50" in request.url
    assert request.cache_seconds == 15 * 60
    assert request.secret_headers == {
        "User-Agent": "/prod/sources/usajobs/user-agent",
        "Authorization-Key": "/prod/sources/usajobs/api-key",
    }


def test_usajobs_refuses_search_until_enabled() -> None:
    with pytest.raises(AppError) as error:
        USAJobsAdapter(Settings()).build_search_request(
            "usajobs",
            SearchQuery(("Python",), None, None, 30),
        )

    assert error.value.code == "SOURCE_NOT_CONFIGURED"


def test_usajobs_parses_full_synthetic_fixture_with_attribution_link() -> None:
    fixture = Path("tests/fixtures/usajobs/search.json").read_text(encoding="utf-8")

    jobs = USAJobsAdapter(Settings(usajobs_enabled=True)).discover_jobs(fixture)

    assert len(jobs) == 1
    assert jobs[0].external_id == "81000100"
    assert jobs[0].url == "https://www.usajobs.gov/job/81000100"
    assert jobs[0].company == "Synthetic Federal Digital Service"
    assert jobs[0].location_raw == "Washington, District of Columbia"
    assert "PostgreSQL" in jobs[0].description
    assert "United States Citizens" in jobs[0].description
    assert jobs[0].posted_at is not None
