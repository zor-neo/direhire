from urllib.parse import parse_qs, urlsplit

from direhire.errors import AppError
from direhire.sources.adapters._shared import (
    json_document,
    parse_iso_datetime,
    public_endpoint,
    text,
)
from direhire.sources.contracts import AdapterCapabilities, DiscoveredJob


class WorkableAdapter:
    """Public Workable careers widget with descriptions explicitly requested."""

    key = "workable"
    capabilities = AdapterCapabilities(False, False, False, False, True)

    def validate_source(self, source_url: str | None) -> None:
        normalized = public_endpoint(
            source_url,
            hosts={"apply.workable.com"},
            path_pattern=r"/api/v1/widget/accounts/[^/]+/?",
        )
        if parse_qs(urlsplit(normalized).query).get("details") != ["true"]:
            raise AppError(
                "SOURCE_URL_INVALID",
                "The Workable feed URL must include details=true.",
                422,
            )

    def discover_jobs(self, content: str, source_url: str | None = None) -> list[DiscoveredJob]:
        del source_url
        document = json_document(content)
        if not isinstance(document, dict) or not isinstance(document.get("jobs"), list):
            return []
        company = text(document.get("name")) or "Employer"
        jobs: list[DiscoveredJob] = []
        for item in document["jobs"]:
            if not isinstance(item, dict):
                continue
            location = _location(item)
            values = (
                text(item.get("shortcode")),
                text(item.get("url")) or text(item.get("shortlink")),
                text(item.get("title")),
                company,
                location,
                text(item.get("description")),
            )
            if all(values):
                jobs.append(
                    DiscoveredJob(
                        *values,
                        posted_at=parse_iso_datetime(
                            item.get("published_on") or item.get("created_at")
                        ),
                    )
                )
        return jobs

    def health_check(self, content: str) -> bool:
        document = json_document(content)
        return (
            isinstance(document, dict)
            and isinstance(document.get("name"), str)
            and isinstance(document.get("jobs"), list)
        )


def _location(item: dict[str, object]) -> str:
    locations = item.get("locations")
    if isinstance(locations, list):
        labels: list[str] = []
        for value in locations:
            if not isinstance(value, dict):
                continue
            label = ", ".join(
                part for part in (text(value.get("city")), text(value.get("country"))) if part
            )
            if label and label not in labels:
                labels.append(label)
        if labels:
            return "; ".join(labels)
    return ", ".join(
        part for part in (text(item.get("city")), text(item.get("country"))) if part
    ) or ("Remote" if item.get("telecommuting") else "Location not stated")
