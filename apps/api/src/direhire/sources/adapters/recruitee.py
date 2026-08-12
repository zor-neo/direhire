from urllib.parse import urlsplit

from direhire.sources.adapters._shared import (
    json_document,
    parse_iso_datetime,
    public_endpoint,
    text,
)
from direhire.sources.contracts import AdapterCapabilities, DiscoveredJob


class RecruiteeAdapter:
    key = "recruitee"
    capabilities = AdapterCapabilities(False, True, False, False, True)

    def validate_source(self, source_url: str | None) -> None:
        public_endpoint(source_url, host_suffix=".recruitee.com", path_pattern=r"/api/offers/?")

    def discover_jobs(self, content: str, source_url: str | None = None) -> list[DiscoveredJob]:
        document = json_document(content)
        offers = document.get("offers") if isinstance(document, dict) else None
        if not isinstance(offers, list):
            return []
        company = _company(source_url)
        jobs: list[DiscoveredJob] = []
        for item in offers:
            if not isinstance(item, dict):
                continue
            locations = item.get("locations")
            location = text(item.get("location"))
            if not location and isinstance(locations, list):
                location = ", ".join(
                    text(value.get("name"))
                    for value in locations
                    if isinstance(value, dict) and value.get("name")
                )
            values = (
                text(item.get("id")) or text(item.get("slug")),
                text(item.get("careers_url")) or text(item.get("url")),
                text(item.get("title")),
                text(item.get("company_name")) or company,
                location,
                text(item.get("description")) or text(item.get("description_plain")),
            )
            if all(values):
                jobs.append(
                    DiscoveredJob(*values, posted_at=parse_iso_datetime(item.get("published_at")))
                )
        return jobs

    def health_check(self, content: str) -> bool:
        document = json_document(content)
        return isinstance(document, dict) and isinstance(document.get("offers"), list)


def _company(url: str | None) -> str:
    host = urlsplit(url or "").hostname or ""
    return host.removesuffix(".recruitee.com").replace("-", " ").title() or "Employer"
