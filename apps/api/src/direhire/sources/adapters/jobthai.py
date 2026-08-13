from __future__ import annotations

import json
from datetime import datetime

from direhire.errors import AppError
from direhire.sources.contracts import (
    AdapterCapabilities,
    DiscoveredJob,
    SearchQuery,
    SearchRequest,
)


class JobThaiAdapter:
    """Public JobThai keyword-search adapter backed by its web GraphQL response."""

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
