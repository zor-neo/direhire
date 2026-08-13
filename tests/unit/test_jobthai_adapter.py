import os

from direhire.sources.adapters.jobthai import JobThaiAdapter
from direhire.sources.canonicalization import canonicalize_jobthai_url

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures", "jobthai", "1945537")


def test_canonicalize_jobthai_url() -> None:
    res = canonicalize_jobthai_url("https://www.jobthai.com/en/company/job/1945537")
    assert res is not None
    job_id, canonical_url = res
    assert job_id == "1945537"
    assert canonical_url == "https://www.jobthai.com/en/job/1945537"


def test_jobthai_adapter_parses_job_page_fixture() -> None:
    job_page_path = os.path.join(FIXTURES_DIR, "job-page.html")
    assert os.path.exists(job_page_path), "job-page.html fixture must exist"

    with open(job_page_path, encoding="utf-8") as f:
        html_content = f.read()

    adapter = JobThaiAdapter()
    facts, extracted_text = adapter.parse_job_detail(
        html_content, "https://www.jobthai.com/en/job/1945537"
    )

    assert facts.external_job_id == "1945537"
    assert facts.canonical_url == "https://www.jobthai.com/en/job/1945537"
    assert "IT Support" in str(facts.title)
    assert "โนส ที" in str(facts.company) or "Nose tea" in str(facts.company)

    # Unmistakable phrase presence check on extracted text
    assert "เดินสาย LAN" in extracted_text
    assert "อายุระหว่าง 22-30 ปี" in extracted_text


def test_jobthai_adapter_parses_company_page_json_ld_fallback() -> None:
    company_page_path = os.path.join(FIXTURES_DIR, "company-page.html")
    assert os.path.exists(company_page_path), "company-page.html fixture must exist"

    with open(company_page_path, encoding="utf-8") as f:
        html_content = f.read()

    adapter = JobThaiAdapter()
    facts, extracted_text = adapter.parse_job_detail(
        html_content, "https://www.jobthai.com/en/company/job/1945537"
    )

    assert facts.external_job_id == "1945537"
    assert facts.canonical_url == "https://www.jobthai.com/en/job/1945537"

    # JSON-LD fallback must extract qualifications and responsibilities
    assert "เดินสาย LAN" in extracted_text
    assert "อายุระหว่าง 22-30 ปี" in extracted_text
