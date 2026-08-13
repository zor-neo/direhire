from __future__ import annotations

from direhire.errors import AppError
from direhire.sources.adapters._shared import json_document, parse_iso_datetime, text
from direhire.sources.contracts import (
    AdapterCapabilities,
    DiscoveredJob,
    SearchQuery,
    SearchRequest,
)


class RemotiveAdapter:
    """Shared public Remotive corpus with mandatory source links and attribution."""

    key = "remotive"
    endpoint = "https://remotive.com/api/remote-jobs"
    capabilities = AdapterCapabilities(False, False, False, False, True)

    def validate_source(self, source_url: str | None) -> None:
        if source_url is not None:
            raise AppError("SOURCE_UNSUPPORTED", "Remotive search does not accept a URL.", 422)

    def build_search_request(self, platform_key: str, query: SearchQuery) -> SearchRequest:
        del query
        if platform_key != "remotive":
            raise AppError("SOURCE_UNSUPPORTED", "This adapter only supports Remotive.", 422)
        # Remotive recommends no more than four corpus fetches per day. Every
        # Watch shares the same unfiltered request and six-hour cache.
        return SearchRequest(
            method="GET",
            url=self.endpoint,
            headers={"Accept": "application/json"},
            cache_seconds=6 * 60 * 60,
        )

    def discover_jobs(self, content: str, source_url: str | None = None) -> list[DiscoveredJob]:
        del source_url
        document = json_document(content)
        values = document.get("jobs") if isinstance(document, dict) else None
        if not isinstance(values, list):
            raise AppError("SOURCE_RESPONSE_INVALID", "Remotive job data is missing.", 503)
        jobs: list[DiscoveredJob] = []
        for item in values:
            if not isinstance(item, dict):
                continue
            external_id = text(item.get("id"))
            url = text(item.get("url"))
            title = text(item.get("title"))
            company = text(item.get("company_name"))
            description = text(item.get("description"))
            location = text(item.get("candidate_required_location")) or "Remote"
            if not all((external_id, url, title, company, description)):
                continue
            if not url.startswith("https://remotive.com/"):
                continue
            jobs.append(
                DiscoveredJob(
                    external_id=external_id,
                    url=url,
                    title=title,
                    company=company,
                    location_raw=location,
                    description=description,
                    posted_at=parse_iso_datetime(item.get("publication_date")),
                )
            )
        return jobs

    def health_check(self, content: str) -> bool:
        try:
            document = json_document(content)
        except AppError:
            return False
        return isinstance(document, dict) and isinstance(document.get("jobs"), list)
