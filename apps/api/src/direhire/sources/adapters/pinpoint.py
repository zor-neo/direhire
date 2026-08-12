from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from xml.etree import ElementTree

from direhire.errors import AppError
from direhire.sources.adapters._shared import public_endpoint, text
from direhire.sources.contracts import AdapterCapabilities, DiscoveredJob


class PinpointAdapter:
    key = "pinpoint"
    capabilities = AdapterCapabilities(False, False, False, False, True)

    def validate_source(self, source_url: str | None) -> None:
        public_endpoint(source_url, host_suffix=".pinpointhq.com", path_pattern=r"/jobs\.rss")

    def discover_jobs(self, content: str, source_url: str | None = None) -> list[DiscoveredJob]:
        root = _xml(content)
        company = _company(source_url)
        jobs: list[DiscoveredJob] = []
        for item in root.findall(".//item"):
            link = _value(item, "link")
            values = (
                _value(item, "guid") or link.rstrip("/").rsplit("/", 1)[-1],
                link,
                _value(item, "title"),
                company,
                _encoded_field(item, "Location"),
                _value(item, "description") or _encoded(item),
            )
            if all(values):
                jobs.append(DiscoveredJob(*values, posted_at=_date(_value(item, "pubDate"))))
        return jobs

    def health_check(self, content: str) -> bool:
        return _xml(content).tag.casefold().endswith("rss")


def _xml(content: str) -> ElementTree.Element:
    try:
        return ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise AppError("SOURCE_RESPONSE_INVALID", "The source returned invalid data.", 502) from exc


def _value(element: ElementTree.Element, name: str) -> str:
    node = element.find(name)
    return text(node.text if node is not None else None)


def _encoded(item: ElementTree.Element) -> str:
    for child in item:
        if child.tag.endswith("encoded"):
            return text(child.text)
    return ""


def _encoded_field(item: ElementTree.Element, label: str) -> str:
    content = _encoded(item)
    marker = f"<strong>{label}: </strong>"
    if marker not in content:
        return ""
    return content.split(marker, 1)[1].split("</p>", 1)[0].strip()


def _date(value: str) -> datetime | None:
    try:
        return parsedate_to_datetime(value) if value else None
    except (TypeError, ValueError):
        return None


def _company(url: str | None) -> str:
    host = urlsplit(url or "").hostname or ""
    return host.removesuffix(".pinpointhq.com").replace("-", " ").title() or "Employer"
