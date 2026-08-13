from direhire.config import Settings
from direhire.sources.contracts import SearchRequest
from direhire.sources.http_fetcher import SafePublicFetcher


class FakeSecrets:
    values = {
        "/sources/usajobs/user-agent": "api-owner@example.invalid",
        "/sources/usajobs/api-key": "test-key",
    }

    def get(self, parameter_name: str) -> str:
        return self.values[parameter_name]


def test_fetcher_resolves_secret_headers_only_at_request_time(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class Response:
        headers = {"Content-Type": "application/json"}

        def raise_for_status(self) -> None:
            pass

        def iter_bytes(self):
            yield b'{"SearchResult": {"SearchResultItems": []}}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    class Client:
        def __init__(self, **kwargs):
            del kwargs

        def stream(self, method, url, headers, content):
            del method, url, content
            captured.update(headers)
            return Response()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    monkeypatch.setattr("direhire.sources.http_fetcher.httpx.Client", Client)
    monkeypatch.setattr(SafePublicFetcher, "_validate_dns", staticmethod(lambda url: None))
    request = SearchRequest(
        method="GET",
        url="https://data.usajobs.gov/api/search?Keyword=Python",
        headers={"Accept": "application/json"},
        secret_headers={
            "User-Agent": "/sources/usajobs/user-agent",
            "Authorization-Key": "/sources/usajobs/api-key",
        },
    )

    result = SafePublicFetcher(Settings(), FakeSecrets()).fetch_request(request)

    assert "SearchResultItems" in result
    assert captured["User-Agent"] == "api-owner@example.invalid"
    assert captured["Authorization-Key"] == "test-key"
