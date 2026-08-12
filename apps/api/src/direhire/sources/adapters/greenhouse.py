from urllib.parse import parse_qs, urlsplit

from direhire.errors import AppError
from direhire.sources.adapters._shared import (
    json_document,
    parse_iso_datetime,
    public_endpoint,
    text,
)
from direhire.sources.contracts import AdapterCapabilities, DiscoveredJob


class GreenhouseAdapter:
    key = "greenhouse"
    capabilities = AdapterCapabilities(True, False, False, False, True)

    def validate_source(self, source_url: str | None) -> None:
        normalized = public_endpoint(
            source_url,
            hosts={"boards-api.greenhouse.io"},
            path_pattern=r"/v1/boards/[^/]+/jobs/?",
        )
        if parse_qs(urlsplit(normalized).query).get("content") != ["true"]:
            raise AppError(
                "SOURCE_URL_INVALID",
                "The Greenhouse feed URL must include content=true.",
                422,
            )

    def discover_jobs(self, content: str, source_url: str | None = None) -> list[DiscoveredJob]:
        document = json_document(content)
        if not isinstance(document, dict) or not isinstance(document.get("jobs"), list):
            return []
        board = _path_token(source_url, -2)
        jobs: list[DiscoveredJob] = []
        for item in document["jobs"]:
            if not isinstance(item, dict):
                continue
            location = item.get("location") or {}
            values = (
                text(item.get("id")),
                text(item.get("absolute_url")),
                text(item.get("title")),
                text(item.get("company_name")) or board,
                text(location.get("name")) if isinstance(location, dict) else "",
                text(item.get("content")),
            )
            if all(values):
                jobs.append(
                    DiscoveredJob(
                        *values, posted_at=parse_iso_datetime(item.get("first_published"))
                    )
                )
        return jobs

    def health_check(self, content: str) -> bool:
        document = json_document(content)
        return isinstance(document, dict) and isinstance(document.get("jobs"), list)


def _path_token(url: str | None, index: int) -> str:
    parts = [part for part in urlsplit(url or "").path.split("/") if part]
    try:
        return parts[index].replace("-", " ").replace("_", " ").title()
    except IndexError:
        return "Employer"
