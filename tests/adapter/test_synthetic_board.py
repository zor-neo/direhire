from pathlib import Path

from direhire.sources.adapters.synthetic_board import SyntheticBoardAdapter


def test_fixture_adapter_extracts_valid_jobs_and_skips_malformed_cards() -> None:
    fixture = Path("tests/fixtures/synthetic_board/jobs.html").read_text(encoding="utf-8")
    adapter = SyntheticBoardAdapter()
    jobs = adapter.discover_jobs(fixture)
    assert len(jobs) == 1
    assert jobs[0].external_id == "synthetic-001"
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].company == "Northstar Labs"
    assert "PostgreSQL" in jobs[0].description
    assert adapter.health_check(fixture) is True
