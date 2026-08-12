from urllib.parse import urlsplit
from xml.etree import ElementTree

from direhire.errors import AppError
from direhire.sources.adapters._shared import public_endpoint, text
from direhire.sources.contracts import AdapterCapabilities, DiscoveredJob


class PersonioAdapter:
    key = "personio"
    capabilities = AdapterCapabilities(False, False, False, False, True)

    def validate_source(self, source_url: str | None) -> None:
        public_endpoint(source_url, host_suffix=".jobs.personio.de", path_pattern=r"/xml/?")

    def discover_jobs(self, content: str, source_url: str | None = None) -> list[DiscoveredJob]:
        root = _xml(content)
        company = _company(source_url)
        jobs: list[DiscoveredJob] = []
        for position in root.findall(".//position"):
            descriptions = [
                description
                for node in position.findall(".//jobDescription")
                if (description := _description(node))
            ]
            external_id = _value(position, "id")
            values = (
                external_id,
                _value(position, "url") or _job_url(source_url, external_id),
                _value(position, "name"),
                company,
                _value(position, "office"),
                "\n".join(descriptions),
            )
            if all(values):
                jobs.append(DiscoveredJob(*values))
        return jobs

    def health_check(self, content: str) -> bool:
        root = _xml(content)
        return root.tag.casefold() == "workzag-jobs" or root.find(".//position") is not None


def _xml(content: str) -> ElementTree.Element:
    try:
        return ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise AppError("SOURCE_RESPONSE_INVALID", "The source returned invalid data.", 502) from exc


def _value(element: ElementTree.Element, name: str) -> str:
    node = element.find(name)
    return text(node.text if node is not None else None)


def _description(element: ElementTree.Element) -> str:
    value = element.find("value")
    if value is not None:
        return " ".join(part.strip() for part in value.itertext() if part.strip())
    return " ".join(part.strip() for part in element.itertext() if part.strip())


def _job_url(source_url: str | None, external_id: str) -> str:
    parsed = urlsplit(source_url or "")
    return f"{parsed.scheme}://{parsed.netloc}/job/{external_id}" if parsed.netloc else ""


def _company(url: str | None) -> str:
    host = urlsplit(url or "").hostname or ""
    return host.removesuffix(".jobs.personio.de").replace("-", " ").title() or "Employer"
