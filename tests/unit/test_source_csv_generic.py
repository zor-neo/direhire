import pytest
from direhire.errors import AppError
from direhire.sources.adapters.generic_public import GenericPublicAdapter
from direhire.sources.csv_import import parse_source_csv


def test_source_csv_is_strict_and_normalizes_public_urls() -> None:
    rows = parse_source_csv(
        b"source_kind,adapter_key,url\r\nCUSTOM_URL,generic_public,https://jobs.example.invalid/openings#top\r\n"
    )
    assert len(rows) == 1
    assert rows[0].url == "https://jobs.example.invalid/openings"
    with pytest.raises(AppError):
        parse_source_csv(b"adapter_key,url\nfoo,https://example.invalid\n")


def test_generic_adapter_extracts_only_complete_schema_org_jobs() -> None:
    html = """
    <script type="application/ld+json">
    {"@type":"JobPosting","identifier":{"value":"req-1"},
     "url":"https://jobs.example.invalid/req-1","title":"Cloud Engineer",
     "hiringOrganization":{"name":"Northstar Labs"},
     "jobLocation":{"address":{"addressLocality":"Bangkok","addressCountry":"TH"}},
     "description":"Build secure cloud platforms with Python."}
    </script>
    """
    jobs = GenericPublicAdapter().discover_jobs(html)
    assert len(jobs) == 1
    assert jobs[0].location_raw == "Bangkok, TH"
