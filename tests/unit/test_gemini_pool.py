import pytest
from direhire.ai.providers import (
    GeminiCredential,
    GeminiPoolProvider,
    ProviderFailure,
    ProviderUsage,
)
from direhire.errors import AppError
from direhire.models import AiProviderRoute
from sqlalchemy.orm import Session, sessionmaker


class FakeTransport:
    def __init__(self, failing_keys: set[str] | None = None) -> None:
        self.calls: list[str] = []
        self.failing_keys = failing_keys or set()

    def generate(self, **kwargs: object) -> tuple[str, ProviderUsage]:
        api_key = str(kwargs["api_key"])
        self.calls.append(api_key)
        if api_key in self.failing_keys:
            raise ProviderFailure("AI_RATE_LIMITED", retryable=True, rate_limited=True)
        return "{}", ProviderUsage(10, 5, 15)


def credentials() -> list[GeminiCredential]:
    return [
        GeminiCredential("project-a", "key-a"),
        GeminiCredential("project-b", "key-b"),
        GeminiCredential("project-c", "key-c"),
    ]


def test_gemini_pool_rotates_and_cools_down_rate_limited_project(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as database:
        transport = FakeTransport({"key-a"})
        pool = GeminiPoolProvider(database, credentials(), transport)
        first = pool.generate(
            model="test-model", prompt="public", response_schema={}, max_output_tokens=100
        )
        second = pool.generate(
            model="test-model", prompt="public", response_schema={}, max_output_tokens=100
        )

        assert first.route_key == "project-b"
        assert second.route_key == "project-c"
        assert transport.calls == ["key-a", "key-b", "key-c"]
        route_a = database.get(AiProviderRoute, "project-a")
        assert route_a is not None
        assert route_a.health == "COOLDOWN"
        assert route_a.last_error_code == "AI_RATE_LIMITED"


def test_gemini_pool_requires_exactly_three_distinct_project_routes(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as database, pytest.raises(AppError):
        GeminiPoolProvider(database, credentials()[:2], FakeTransport())
