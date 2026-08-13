from html.parser import HTMLParser

from direhire.errors import AppError
from direhire.sources.contracts import AdapterCapabilities, DiscoveredJob


class SyntheticBoardAdapter:
    """Fixture-only launch adapter used to prove the safe adapter boundary."""

    key = "synthetic_board"
    capabilities = AdapterCapabilities(
        pagination=False,
        keyword_search=True,
        location_search=True,
        browser_required=False,
        full_description=True,
    )

    def validate_source(self, source_url: str | None) -> None:
        if source_url is not None and not source_url.startswith(
            "https://synthetic.example.invalid/"
        ):
            raise AppError("SOURCE_UNSUPPORTED", "This synthetic source URL is invalid.", 422)

    def discover_jobs(self, content: str, source_url: str | None = None) -> list[DiscoveredJob]:
        parser = _JobParser()
        parser.feed(content)
        jobs: list[DiscoveredJob] = []
        for item in parser.jobs:
            required = ("external_id", "url", "title", "company", "location", "description")
            if not all(item.get(key) for key in required):
                continue
            jobs.append(
                DiscoveredJob(
                    external_id=item["external_id"],
                    url=item["url"],
                    title=item["title"],
                    company=item["company"],
                    location_raw=item["location"],
                    description=item["description"],
                )
            )
        return jobs

    def health_check(self, content: str) -> bool:
        return bool(self.discover_jobs(content))


class _JobParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.jobs: list[dict[str, str]] = []
        self.current: dict[str, str] | None = None
        self.field: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "article" and attributes.get("data-job-id"):
            self.current = {"external_id": attributes["data-job-id"] or ""}
        if self.current is not None and (field := attributes.get("data-field")):
            self.field = field
            if field == "url" and attributes.get("href"):
                self.current[field] = attributes["href"] or ""

    def handle_data(self, data: str) -> None:
        if self.current is not None and self.field:
            self.current[self.field] = f"{self.current.get(self.field, '')} {data}".strip()

    def handle_endtag(self, tag: str) -> None:
        if tag == "article" and self.current is not None:
            self.jobs.append(self.current)
            self.current = None
        self.field = None
