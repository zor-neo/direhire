from __future__ import annotations

from urllib.parse import urlencode

from direhire.config import Settings
from direhire.errors import AppError
from direhire.sources.adapters._shared import json_document, parse_iso_datetime, text
from direhire.sources.contracts import (
    AdapterCapabilities,
    DiscoveredJob,
    SearchQuery,
    SearchRequest,
)


class USAJobsAdapter:
    """Official USAJOBS Search API adapter for current public announcements."""

    key = "usajobs"
    endpoint = "https://data.usajobs.gov/api/search"
    capabilities = AdapterCapabilities(True, True, True, False, True)

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def validate_source(self, source_url: str | None) -> None:
        if source_url is not None:
            raise AppError("SOURCE_UNSUPPORTED", "USAJOBS search does not accept a URL.", 422)

    def build_search_request(self, platform_key: str, query: SearchQuery) -> SearchRequest:
        if platform_key != self.key:
            raise AppError("SOURCE_UNSUPPORTED", "This adapter only supports USAJOBS.", 422)
        if not self.settings.usajobs_enabled:
            raise AppError(
                "SOURCE_NOT_CONFIGURED",
                "USAJOBS discovery is not configured.",
                503,
            )
        parameters: dict[str, str | int] = {
            "Keyword": " ".join(query.keywords),
            "WhoMayApply": "Public",
            "Fields": "Full",
            "ResultsPerPage": 50,
            "Page": max(1, query.page),
        }
        if query.location and query.location.casefold() not in {
            "united states",
            "usa",
            "us",
        }:
            parameters["LocationName"] = query.location
        if query.posting_age_days is not None:
            parameters["DatePosted"] = min(60, max(0, query.posting_age_days))
        return SearchRequest(
            method="GET",
            url=f"{self.endpoint}?{urlencode(parameters)}",
            headers={"Accept": "application/json"},
            cache_seconds=15 * 60,
            secret_headers={
                "User-Agent": self.settings.usajobs_user_agent_parameter,
                "Authorization-Key": self.settings.usajobs_api_key_parameter,
            },
        )

    def discover_jobs(self, content: str, source_url: str | None = None) -> list[DiscoveredJob]:
        del source_url
        document = json_document(content)
        result = document.get("SearchResult") if isinstance(document, dict) else None
        items = result.get("SearchResultItems") if isinstance(result, dict) else None
        if not isinstance(items, list):
            raise AppError("SOURCE_RESPONSE_INVALID", "USAJOBS search data is missing.", 503)
        jobs: list[DiscoveredJob] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            descriptor = item.get("MatchedObjectDescriptor")
            if not isinstance(descriptor, dict):
                continue
            external_id = text(item.get("MatchedObjectId")) or text(descriptor.get("PositionID"))
            url = text(descriptor.get("PositionURI"))
            title = text(descriptor.get("PositionTitle"))
            company = text(descriptor.get("OrganizationName")) or text(
                descriptor.get("DepartmentName")
            )
            location = text(descriptor.get("PositionLocationDisplay")) or _locations(descriptor)
            description = _description(descriptor)
            if not all((external_id, url, title, company, location, description)):
                continue
            if not url.startswith("https://www.usajobs.gov/"):
                continue
            jobs.append(
                DiscoveredJob(
                    external_id=external_id,
                    url=url,
                    title=title,
                    company=company,
                    location_raw=location,
                    description=description,
                    posted_at=parse_iso_datetime(descriptor.get("PublicationStartDate")),
                )
            )
        return jobs

    def health_check(self, content: str) -> bool:
        try:
            document = json_document(content)
        except AppError:
            return False
        result = document.get("SearchResult") if isinstance(document, dict) else None
        return isinstance(result, dict) and isinstance(result.get("SearchResultItems"), list)


def _locations(descriptor: dict[str, object]) -> str:
    values = descriptor.get("PositionLocation")
    if not isinstance(values, list):
        return ""
    labels = [
        text(value.get("LocationName"))
        for value in values
        if isinstance(value, dict) and value.get("LocationName")
    ]
    return "; ".join(dict.fromkeys(labels))


def _description(descriptor: dict[str, object]) -> str:
    parts = [text(descriptor.get("QualificationSummary"))]
    formatted = descriptor.get("PositionFormattedDescription")
    if isinstance(formatted, list):
        parts.extend(
            text(value.get("Content"))
            for value in formatted
            if isinstance(value, dict) and value.get("Content")
        )
    user_area = descriptor.get("UserArea")
    details = user_area.get("Details") if isinstance(user_area, dict) else None
    if isinstance(details, dict):
        for key in (
            "JobSummary",
            "MajorDuties",
            "Requirements",
            "Education",
            "Evaluations",
            "OtherInformation",
        ):
            parts.append(text(details.get(key)))
        who_may_apply = details.get("WhoMayApply")
        if isinstance(who_may_apply, dict):
            parts.append(text(who_may_apply.get("Name")))
    return "\n\n".join(part for part in parts if part)
