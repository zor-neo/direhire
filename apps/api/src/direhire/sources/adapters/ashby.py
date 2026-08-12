from urllib.parse import urlsplit

from direhire.sources.adapters._shared import (
    json_document,
    parse_iso_datetime,
    public_endpoint,
    text,
)
from direhire.sources.contracts import AdapterCapabilities, DiscoveredJob


class AshbyAdapter:
    key = "ashby"
    capabilities = AdapterCapabilities(False, False, False, False, True)

    def validate_source(self, source_url: str | None) -> None:
        public_endpoint(
            source_url,
            hosts={"api.ashbyhq.com"},
            path_pattern=r"/posting-api/job-board/[^/]+/?",
        )

    def discover_jobs(self, content: str, source_url: str | None = None) -> list[DiscoveredJob]:
        document = json_document(content)
        if not isinstance(document, dict) or not isinstance(document.get("jobs"), list):
            return []
        company = _board(source_url)
        jobs: list[DiscoveredJob] = []
        for item in document["jobs"]:
            if not isinstance(item, dict) or item.get("isListed") is False:
                continue
            values = (
                text(item.get("id")) or text(item.get("jobUrl")).rstrip("/").rsplit("/", 1)[-1],
                text(item.get("jobUrl")),
                text(item.get("title")),
                text(item.get("company")) or company,
                text(item.get("location")),
                text(item.get("descriptionPlain")) or text(item.get("descriptionHtml")),
            )
            if all(values):
                jobs.append(
                    DiscoveredJob(*values, posted_at=parse_iso_datetime(item.get("publishedAt")))
                )
        return jobs

    def health_check(self, content: str) -> bool:
        document = json_document(content)
        return isinstance(document, dict) and isinstance(document.get("jobs"), list)


def _board(url: str | None) -> str:
    parts = [part for part in urlsplit(url or "").path.split("/") if part]
    return (parts[-1] if parts else "Employer").replace("-", " ").title()
