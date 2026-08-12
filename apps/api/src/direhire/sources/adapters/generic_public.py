import json
from contextlib import suppress
from html.parser import HTMLParser

from direhire.sources.contracts import AdapterCapabilities, DiscoveredJob
from direhire.sources.validation import normalize_public_url


class GenericPublicAdapter:
    key = "generic_public"
    capabilities = AdapterCapabilities(
        pagination=False,
        keyword_search=False,
        location_search=False,
        browser_required=False,
        full_description=True,
    )

    def validate_source(self, source_url: str | None) -> None:
        if not source_url:
            raise ValueError("generic source requires a URL")
        normalize_public_url(source_url)

    def discover_jobs(self, content: str, source_url: str | None = None) -> list[DiscoveredJob]:
        parser = _JsonLdParser()
        parser.feed(content)
        jobs: list[DiscoveredJob] = []
        for document in parser.documents:
            items = document if isinstance(document, list) else [document]
            for item in items:
                if not isinstance(item, dict) or item.get("@type") != "JobPosting":
                    continue
                organization = item.get("hiringOrganization") or {}
                location = item.get("jobLocation") or {}
                address = location.get("address") if isinstance(location, dict) else {}
                if not isinstance(organization, dict) or not isinstance(address, dict):
                    continue
                values = {
                    "external_id": str(item.get("identifier", {}).get("value", ""))
                    if isinstance(item.get("identifier"), dict)
                    else "",
                    "url": str(item.get("url", "")),
                    "title": str(item.get("title", "")),
                    "company": str(organization.get("name", "")),
                    "location": ", ".join(
                        str(address.get(key, ""))
                        for key in ("addressLocality", "addressCountry")
                        if address.get(key)
                    ),
                    "description": str(item.get("description", "")),
                }
                if all(values.values()):
                    jobs.append(
                        DiscoveredJob(
                            external_id=values["external_id"],
                            url=values["url"],
                            title=values["title"],
                            company=values["company"],
                            location_raw=values["location"],
                            description=values["description"],
                        )
                    )
        return jobs

    def health_check(self, content: str) -> bool:
        return bool(self.discover_jobs(content))


class _JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.capture = False
        self.buffer: list[str] = []
        self.documents: list[object] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        self.capture = tag == "script" and attributes.get("type") == "application/ld+json"
        if self.capture:
            self.buffer = []

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.capture:
            with suppress(json.JSONDecodeError):
                self.documents.append(json.loads("".join(self.buffer)))
            self.capture = False
