from urllib.parse import parse_qs, urlsplit

from direhire.errors import AppError
from direhire.sources.adapters._shared import json_document, public_endpoint, text
from direhire.sources.contracts import AdapterCapabilities, DiscoveredJob


class LeverAdapter:
    key = "lever"
    capabilities = AdapterCapabilities(True, True, True, False, True)

    def validate_source(self, source_url: str | None) -> None:
        normalized = public_endpoint(
            source_url,
            hosts={"api.lever.co", "api.eu.lever.co"},
            path_pattern=r"/v0/postings/[^/]+/?",
        )
        if parse_qs(urlsplit(normalized).query).get("mode") != ["json"]:
            raise AppError("SOURCE_URL_INVALID", "The Lever feed URL must include mode=json.", 422)

    def discover_jobs(self, content: str, source_url: str | None = None) -> list[DiscoveredJob]:
        document = json_document(content)
        if not isinstance(document, list):
            return []
        company = _site(source_url)
        jobs: list[DiscoveredJob] = []
        for item in document:
            if not isinstance(item, dict):
                continue
            categories = item.get("categories") or {}
            values = (
                text(item.get("id")),
                text(item.get("hostedUrl")),
                text(item.get("text")),
                text(item.get("company")) or company,
                text(categories.get("location")) if isinstance(categories, dict) else "",
                text(item.get("descriptionPlain")) or text(item.get("description")),
            )
            if all(values):
                jobs.append(DiscoveredJob(*values))
        return jobs

    def health_check(self, content: str) -> bool:
        return isinstance(json_document(content), list)


def _site(url: str | None) -> str:
    parts = [part for part in urlsplit(url or "").path.split("/") if part]
    return (parts[-1] if parts else "Employer").replace("-", " ").title()
