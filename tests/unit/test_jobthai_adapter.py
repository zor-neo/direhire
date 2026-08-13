import json
from pathlib import Path

from direhire.sources.adapters.jobthai import JobThaiAdapter
from direhire.sources.contracts import SearchQuery


def test_jobthai_builds_bounded_public_search_request() -> None:
    request = JobThaiAdapter().build_search_request(
        "jobthai",
        SearchQuery(
            keywords=("Python", "FastAPI"),
            location="Bangkok",
            experience_level="MID",
            posting_age_days=30,
        ),
    )

    assert request.method == "POST"
    assert request.url == "https://api.jobthai.com/v1/graphql"
    assert request.json_body is not None
    variables = request.json_body["variables"]
    assert isinstance(variables, dict)
    assert variables["filter"] == {"l": "en", "page": 1, "keyword": "Python FastAPI"}
    assert "authorization" not in {key.casefold() for key in request.headers}


def test_jobthai_parses_synthetic_search_fixture() -> None:
    fixture = Path("tests/fixtures/jobthai/search.json").read_text(encoding="utf-8")
    jobs = JobThaiAdapter().discover_jobs(fixture)

    assert len(jobs) == 2
    assert jobs[0].external_id == "synthetic-jobthai-001"
    assert jobs[0].url == "https://www.jobthai.com/en/company/job/synthetic-jobthai-001"
    assert jobs[0].location_raw == "Bangkok, Thailand"
    assert "PostgreSQL" in jobs[0].description
    assert jobs[0].posted_at is not None


def test_jobthai_rejects_graphql_errors() -> None:
    assert (
        JobThaiAdapter().health_check(json.dumps({"errors": [{"message": "temporary"}]})) is False
    )
