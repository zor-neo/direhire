from typing import Any

import pytest
from direhire.ai.providers import (
    HttpxOpenRouterTransport,
    OpenRouterPrivateProvider,
    ProviderFailure,
    ProviderUsage,
)
from direhire.models import AiProviderRoute
from sqlalchemy.orm import Session, sessionmaker


class RecordingTransport:
    def __init__(self, *, failure: ProviderFailure | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.failure = failure

    def generate(self, **kwargs: object) -> tuple[str, str, ProviderUsage]:
        self.calls.append(kwargs)
        if self.failure is not None:
            raise self.failure
        return "{}", "anthropic", ProviderUsage(10, 5, 15)


class FakeResponse:
    status_code = 200

    def json(self) -> dict[str, object]:
        return {
            "provider": "anthropic",
            "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        }


class RecordingHttpClient:
    def __init__(self) -> None:
        self.request: dict[str, Any] | None = None

    def __enter__(self) -> "RecordingHttpClient":
        return self

    def __exit__(self, *args: object) -> None:
        del args

    def post(self, endpoint: str, **kwargs: Any) -> FakeResponse:
        self.request = {"endpoint": endpoint, **kwargs}
        return FakeResponse()


def test_openrouter_http_request_enforces_zdr_no_collection_and_approved_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = RecordingHttpClient()
    monkeypatch.setattr("direhire.ai.providers.httpx.Client", lambda **kwargs: client)
    text, provider, usage = HttpxOpenRouterTransport().generate(
        api_key="private-secret",
        model="approved/model",
        prompt="private minimum context",
        response_schema={"type": "object"},
        max_output_tokens=100,
        approved_providers=["anthropic"],
    )

    assert text == "{}" and provider == "anthropic" and usage.total_tokens == 18
    assert client.request is not None
    body = client.request["json"]
    assert body["provider"] == {
        "only": ["anthropic"],
        "allow_fallbacks": True,
        "require_parameters": True,
        "data_collection": "deny",
        "zdr": True,
    }
    assert body["response_format"]["json_schema"]["strict"] is True
    assert client.request["headers"]["Authorization"] == "Bearer private-secret"


def test_private_provider_uses_only_private_route_and_records_health(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as database:
        transport = RecordingTransport()
        provider = OpenRouterPrivateProvider(
            database,
            api_key="secret",
            approved_providers=["anthropic"],
            transport=transport,
        )
        response = provider.generate(
            model="approved/model", prompt="private", response_schema={}, max_output_tokens=100
        )
        route = database.get(AiProviderRoute, "openrouter-private")

        assert response.provider == "OPENROUTER"
        assert response.route_key == "anthropic"
        assert transport.calls[0]["approved_providers"] == ["anthropic"]
        assert route is not None and route.provider == "OPENROUTER"
        assert route.total_tokens == 15


def test_private_provider_failure_cools_only_private_route(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as database:
        provider = OpenRouterPrivateProvider(
            database,
            api_key="secret",
            approved_providers=["anthropic"],
            transport=RecordingTransport(
                failure=ProviderFailure("AI_RATE_LIMITED", retryable=True, rate_limited=True)
            ),
        )
        with pytest.raises(ProviderFailure):
            provider.generate(
                model="approved/model", prompt="private", response_schema={}, max_output_tokens=100
            )
        route = database.get(AiProviderRoute, "openrouter-private")
        assert route is not None
        assert route.health == "COOLDOWN"
        assert database.get(AiProviderRoute, "project-a") is None
