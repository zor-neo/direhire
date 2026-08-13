from pathlib import Path

from direhire.sources.adapters.remotive import RemotiveAdapter
from direhire.sources.contracts import SearchQuery


def test_remotive_builds_shared_rate_safe_request() -> None:
    request = RemotiveAdapter().build_search_request(
        "remotive",
        SearchQuery(
            keywords=("Python",),
            location="Worldwide",
            experience_level=None,
            posting_age_days=14,
        ),
    )

    assert request.method == "GET"
    assert request.url == "https://remotive.com/api/remote-jobs"
    assert request.json_body is None
    assert request.cache_seconds == 6 * 60 * 60


def test_remotive_parses_attributed_synthetic_fixture() -> None:
    fixture = Path("tests/fixtures/remotive/jobs.json").read_text(encoding="utf-8")

    jobs = RemotiveAdapter().discover_jobs(fixture)

    assert len(jobs) == 2
    assert jobs[0].external_id == "910001"
    assert jobs[0].url.startswith("https://remotive.com/remote-jobs/")
    assert jobs[0].company == "Synthetic Systems"
    assert jobs[0].location_raw == "Worldwide"
    assert "PostgreSQL" in jobs[0].description
    assert jobs[0].posted_at is not None


def test_remotive_rejects_non_remotive_job_links() -> None:
    content = """{
      "jobs": [{
        "id": 1,
        "url": "https://example.invalid/job/1",
        "title": "Engineer",
        "company_name": "Example",
        "candidate_required_location": "Remote",
        "description": "Python"
      }]
    }"""

    assert RemotiveAdapter().discover_jobs(content) == []
