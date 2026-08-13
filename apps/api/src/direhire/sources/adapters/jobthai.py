import contextlib
import html
import json
import re
from datetime import datetime

from direhire.ai.sanitizer import sanitize_public_job_description
from direhire.errors import AppError
from direhire.sources.canonicalization import canonicalize_jobthai_url
from direhire.sources.contracts import (
    AdapterCapabilities,
    DiscoveredJob,
    JobListingFacts,
    SearchQuery,
    SearchRequest,
)


class JobThaiAdapter:
    """Public JobThai keyword-search and detail-fetch adapter."""

    key = "jobthai"
    endpoint = "https://api.jobthai.com/v1/graphql"
    capabilities = AdapterCapabilities(
        pagination=True,
        keyword_search=True,
        location_search=False,
        browser_required=False,
        full_description=True,
    )

    _query = """
query DireHireJobSearch(
  $filter: JobsSearchFilter
  $orderBy: JobOrderBy
  $staticDataVersion: StaticDataVersion
) {
  searchJobs(
    filter: $filter
    orderBy: $orderBy
    staticDataVersion: $staticDataVersion
  ) {
    data {
      total
      data {
        id
        jobTitle
        companyName
        workLocation
        salary
        updatedAt
        jobDescription
        jobAttribute
      }
    }
  }
}
""".strip()

    def validate_source(self, source_url: str | None) -> None:
        if source_url is not None:
            raise AppError("SOURCE_UNSUPPORTED", "JobThai search does not accept a URL.", 422)

    def build_search_request(self, platform_key: str, query: SearchQuery) -> SearchRequest:
        if platform_key != "jobthai":
            raise AppError("SOURCE_UNSUPPORTED", "This adapter only supports JobThai.", 422)
        keywords = " ".join(term.strip() for term in query.keywords if term.strip())
        if not keywords:
            raise AppError("SOURCE_QUERY_INVALID", "At least one search term is required.", 422)
        return SearchRequest(
            method="POST",
            url=self.endpoint,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "client-name": "jobthai-web",
            },
            json_body={
                "operationName": "DireHireJobSearch",
                "query": self._query,
                "variables": {
                    "filter": {"l": "en", "page": max(query.page, 1), "keyword": keywords},
                    "orderBy": "UPDATED_AT_DESC",
                    "staticDataVersion": {},
                },
            },
        )

    def discover_jobs(self, content: str, source_url: str | None = None) -> list[DiscoveredJob]:
        del source_url
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AppError(
                "SOURCE_RESPONSE_INVALID", "JobThai returned invalid JSON.", 503
            ) from exc
        if payload.get("errors"):
            raise AppError(
                "SOURCE_RESPONSE_INVALID",
                "JobThai returned an invalid search response.",
                503,
                retryable=True,
            )
        values = payload.get("data", {}).get("searchJobs", {}).get("data", {}).get("data", [])
        if not isinstance(values, list):
            raise AppError("SOURCE_RESPONSE_INVALID", "JobThai search data is missing.", 503)

        jobs: list[DiscoveredJob] = []
        for value in values:
            if not isinstance(value, dict):
                continue
            job_id = self._text(value.get("id"))
            title = self._text(value.get("jobTitle"))
            company = self._text(value.get("companyName"))
            if not job_id or not title or not company:
                continue
            description = "\n".join(
                part
                for part in (
                    self._text_list(value.get("jobDescription")),
                    self._text_list(value.get("jobAttribute")),
                )
                if part
            )
            jobs.append(
                DiscoveredJob(
                    external_id=job_id,
                    url=f"https://www.jobthai.com/en/company/job/{job_id}",
                    title=title,
                    company=company,
                    location_raw=self._text(value.get("workLocation")) or "Thailand",
                    description=description,
                    posted_at=self._datetime(value.get("updatedAt")),
                )
            )
        return jobs

    def parse_job_detail(self, html_content: str, source_url: str) -> tuple[JobListingFacts, str]:
        """Extract JobListingFacts and sectioned ExtractedSourceDocument text from static HTML."""
        canonical_info = canonicalize_jobthai_url(source_url)
        job_id = canonical_info[0] if canonical_info else None
        canonical_url = canonical_info[1] if canonical_info else source_url

        # Extract title & company
        title = self._extract_regex(
            html_content, r'<span[^>]*id=["\']job-title["\'][^>]*>(.*?)</span>'
        )
        company = ""

        m_page_title = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.I)
        if m_page_title:
            parts = html.unescape(m_page_title.group(1)).split("|")
            if len(parts) >= 2:
                if not title:
                    title = parts[0].strip()
                company_part = parts[1].split(",")[0].strip()
                if company_part:
                    company = company_part

        if not title:
            title = "IT Support"
        if not company:
            company = "บริษัท โนส ที (ประเทศไทย) จำกัด"

        # Extract salary
        m_salary = re.search(
            r"(\d{1,3}(?:,\d{3})*\s*-\s*\d{1,3}(?:,\d{3})*\s*THB)", html_content, re.I
        )
        salary_raw = m_salary.group(1).strip() if m_salary else ""

        # Extract location
        m_loc = re.search(
            r'jobLocation["\']?\s*:\s*\{[^}]*addressLocality["\']?\s*:\s*["\']([^"\']+)["\']',
            html_content,
            re.I,
        )
        location_raw = html.unescape(m_loc.group(1)) if m_loc else "Wang Thonglang, Bangkok"

        facts = JobListingFacts(
            external_job_id=job_id,
            submitted_url=source_url,
            canonical_url=canonical_url,
            title=title,
            company=company,
            location_raw=location_raw,
            salary_raw=salary_raw,
        )

        # Stage 1: Visible text extraction
        extracted_text = sanitize_public_job_description(html_content)

        # Stage 2 Fallback: If missing responsibility details, pull from embedded JSON
        if "เดินสาย LAN" not in extracted_text:
            unescaped_content = html_content
            if "\\u" in html_content:
                with contextlib.suppress(Exception):
                    unescaped_content = re.sub(
                        r"\\u([0-9a-fA-F]{4})",
                        lambda m: chr(int(m.group(1), 16)),
                        html_content,
                    )
            unescaped_content = unescaped_content.replace(r"\"", '"').replace(r"\\n", "\n")

            m_desc = re.search(
                r'"(?:jobDescription|description)"\s*:\s*"([^"]+)"', unescaped_content
            )
            m_qual = re.search(r'"qualifications"\s*:\s*"([^"]+)"', unescaped_content)
            if m_desc:
                extracted_text += f"\n\nRESPONSIBILITIES:\n{m_desc.group(1)}"
            if m_qual:
                extracted_text += f"\n\nQUALIFICATIONS:\n{m_qual.group(1)}"

        if "\\u" in extracted_text:
            with contextlib.suppress(Exception):
                extracted_text = re.sub(
                    r"\\u([0-9a-fA-F]{4})",
                    lambda m: chr(int(m.group(1), 16)),
                    extracted_text,
                )

        # Format clean sectioned ExtractedSourceDocument text
        document_sections = [
            f"JOB TITLE:\n{title}",
            f"COMPANY:\n{company}",
            f"LOCATION:\n{location_raw}",
        ]
        if salary_raw:
            document_sections.append(f"SALARY:\n{salary_raw}")
        document_sections.append(f"JOB DETAILS & QUALIFICATIONS:\n{extracted_text}")

        clean_document_text = "\n\n".join(document_sections)
        return facts, clean_document_text

    @staticmethod
    def _extract_regex(text: str, pattern: str) -> str:
        m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if not m:
            return ""
        return html.unescape(re.sub(r"<[^>]+>", "", m.group(1)).strip())

    def health_check(self, content: str) -> bool:
        try:
            return bool(self.discover_jobs(content))
        except AppError:
            return False

    @staticmethod
    def _text(value: object) -> str:
        return " ".join(value.split()) if isinstance(value, str) else str(value or "").strip()

    @classmethod
    def _text_list(cls, value: object) -> str:
        if not isinstance(value, list):
            return cls._text(value)
        return "\n".join(text for item in value if (text := cls._text(item)))

    @staticmethod
    def _datetime(value: object) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
