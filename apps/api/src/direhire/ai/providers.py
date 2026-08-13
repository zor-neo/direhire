from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

import httpx
from sqlalchemy.orm import Session

from direhire.errors import AppError
from direhire.models import AiProviderRoute, utcnow


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    prompt_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    text: str
    provider: str
    route_key: str
    model: str
    usage: ProviderUsage


@dataclass(frozen=True, slots=True)
class GeminiCredential:
    route_key: str
    api_key: str


class ProviderFailure(Exception):
    def __init__(self, code: str, *, retryable: bool, rate_limited: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.rate_limited = rate_limited


class GeminiTransport(Protocol):
    def generate(
        self,
        *,
        api_key: str,
        model: str,
        prompt: str,
        response_schema: dict[str, object],
        max_output_tokens: int,
    ) -> tuple[str, ProviderUsage]: ...


class StructuredProvider(Protocol):
    def generate(
        self,
        *,
        model: str,
        prompt: str,
        response_schema: dict[str, object],
        max_output_tokens: int,
    ) -> ProviderResponse: ...


class OpenRouterTransport(Protocol):
    def generate(
        self,
        *,
        api_key: str,
        model: str,
        prompt: str,
        response_schema: dict[str, object],
        max_output_tokens: int,
        approved_providers: list[str],
    ) -> tuple[str, str, ProviderUsage]: ...


class HttpxGeminiTransport:
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def generate(
        self,
        *,
        api_key: str,
        model: str,
        prompt: str,
        response_schema: dict[str, object],
        max_output_tokens: int,
    ) -> tuple[str, ProviderUsage]:
        try:
            with httpx.Client(trust_env=False, timeout=60) as client:
                response = client.post(
                    self.endpoint.format(model=model),
                    headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                    json={
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "responseMimeType": "application/json",
                            "responseJsonSchema": response_schema,
                            "maxOutputTokens": max_output_tokens,
                            "temperature": 0.1,
                        },
                    },
                )
        except httpx.HTTPError as exc:
            raise ProviderFailure("AI_PROVIDER_UNAVAILABLE", retryable=True) from exc
        if response.status_code == 429:
            raise ProviderFailure("AI_RATE_LIMITED", retryable=True, rate_limited=True)
        if response.status_code >= 500:
            raise ProviderFailure("AI_PROVIDER_UNAVAILABLE", retryable=True)
        if response.status_code >= 400:
            raise ProviderFailure("AI_PROVIDER_REJECTED", retryable=False)
        try:
            body = response.json()
            text = body["candidates"][0]["content"]["parts"][0]["text"]
            usage = body.get("usageMetadata", {})
            prompt_tokens = int(usage.get("promptTokenCount", 0))
            output_tokens = int(usage.get("candidatesTokenCount", 0)) + int(
                usage.get("thoughtsTokenCount", 0)
            )
            total_tokens = int(usage.get("totalTokenCount", prompt_tokens + output_tokens))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderFailure("AI_PROVIDER_RESPONSE_INVALID", retryable=True) from exc
        return str(text), ProviderUsage(prompt_tokens, output_tokens, total_tokens)


class GeminiPoolProvider:
    required_routes = ("project-a", "project-b", "project-c")

    def __init__(
        self,
        session: Session,
        credentials: list[GeminiCredential],
        transport: GeminiTransport,
        *,
        cooldown_seconds: int = 60,
    ) -> None:
        credential_map = {credential.route_key: credential for credential in credentials}
        if set(credential_map) != set(self.required_routes):
            raise AppError(
                "AI_CONFIGURATION_INVALID",
                "Public analysis is not configured.",
                503,
                retryable=True,
            )
        self.session = session
        self.credentials = credential_map
        self.transport = transport
        self.cooldown_seconds = cooldown_seconds
        self.cursor = 0

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        response_schema: dict[str, object],
        max_output_tokens: int,
    ) -> ProviderResponse:
        last_failure: ProviderFailure | None = None
        for route_key in self._available_routes():
            route = self._route(route_key)
            route.total_requests += 1
            route.updated_at = utcnow()
            try:
                text, usage = self.transport.generate(
                    api_key=self.credentials[route_key].api_key,
                    model=model,
                    prompt=prompt,
                    response_schema=response_schema,
                    max_output_tokens=max_output_tokens,
                )
            except ProviderFailure as exc:
                last_failure = exc
                route.consecutive_failures += 1
                route.last_error_code = exc.code
                route.health = "COOLDOWN" if exc.retryable else "DEGRADED"
                route.cooldown_until = utcnow() + timedelta(seconds=self.cooldown_seconds)
                continue
            route.health = "HEALTHY"
            route.cooldown_until = None
            route.consecutive_failures = 0
            route.last_error_code = None
            route.total_tokens += usage.total_tokens
            self.cursor = (self.required_routes.index(route_key) + 1) % len(self.required_routes)
            return ProviderResponse(text, "GEMINI", route_key, model, usage)
        if last_failure is not None:
            raise last_failure
        raise ProviderFailure("AI_PUBLIC_ROUTE_UNAVAILABLE", retryable=True)

    def _available_routes(self) -> list[str]:
        now = datetime.now(UTC)
        ordered = [
            self.required_routes[(self.cursor + offset) % len(self.required_routes)]
            for offset in range(len(self.required_routes))
        ]
        available: list[str] = []
        for key in ordered:
            route = self._route(key)
            cooldown_until = route.cooldown_until
            if cooldown_until is not None and cooldown_until.tzinfo is None:
                cooldown_until = cooldown_until.replace(tzinfo=UTC)
            if not route.enabled:
                continue
            if cooldown_until is not None and cooldown_until > now:
                continue
            if route.health == "COOLDOWN":
                route.health = "DEGRADED"
                route.cooldown_until = None
            available.append(key)
        return available

    def _route(self, route_key: str) -> AiProviderRoute:
        route = self.session.get(AiProviderRoute, route_key)
        if route is None:
            route = AiProviderRoute(route_key=route_key, provider="GEMINI")
            self.session.add(route)
            self.session.flush()
        return route


class HttpxOpenRouterTransport:
    endpoint = "https://openrouter.ai/api/v1/chat/completions"

    def generate(
        self,
        *,
        api_key: str,
        model: str,
        prompt: str,
        response_schema: dict[str, object],
        max_output_tokens: int,
        approved_providers: list[str],
    ) -> tuple[str, str, ProviderUsage]:
        try:
            with httpx.Client(trust_env=False, timeout=90) as client:
                response = client.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": {
                                "name": "direhire_private_result",
                                "strict": True,
                                "schema": response_schema,
                            },
                        },
                        "max_completion_tokens": max_output_tokens,
                        "temperature": 0.1,
                        "stream": False,
                        "provider": {
                            "only": approved_providers,
                            "allow_fallbacks": True,
                            "require_parameters": True,
                            "data_collection": "deny",
                            "zdr": True,
                        },
                    },
                )
        except httpx.HTTPError as exc:
            raise ProviderFailure("AI_PRIVATE_PROVIDER_UNAVAILABLE", retryable=True) from exc
        if response.status_code in {402, 429}:
            code = "AI_QUOTA_EXHAUSTED" if response.status_code == 402 else "AI_RATE_LIMITED"
            raise ProviderFailure(code, retryable=True, rate_limited=response.status_code == 429)
        if response.status_code >= 500:
            raise ProviderFailure("AI_PRIVATE_PROVIDER_UNAVAILABLE", retryable=True)
        if response.status_code >= 400:
            raise ProviderFailure("AI_PRIVATE_PROVIDER_REJECTED", retryable=False)
        try:
            body = response.json()
            if "error" in body:
                error_code = int(body["error"].get("code", 500))
                raise ProviderFailure(
                    "AI_RATE_LIMITED" if error_code == 429 else "AI_PRIVATE_PROVIDER_UNAVAILABLE",
                    retryable=True,
                    rate_limited=error_code == 429,
                )
            choice = body["choices"][0]
            if choice.get("finish_reason") == "error" or choice.get("error"):
                raise ProviderFailure("AI_PRIVATE_PROVIDER_UNAVAILABLE", retryable=True)
            text = choice["message"]["content"]
            usage = body.get("usage", {})
            prompt_tokens = int(usage.get("prompt_tokens", 0))
            output_tokens = int(usage.get("completion_tokens", 0))
            total_tokens = int(usage.get("total_tokens", prompt_tokens + output_tokens))
            provider_name = str(body.get("provider", "approved-zdr-route"))
        except ProviderFailure:
            raise
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderFailure("AI_PRIVATE_RESPONSE_INVALID", retryable=True) from exc
        return str(text), provider_name, ProviderUsage(prompt_tokens, output_tokens, total_tokens)


class OpenRouterPrivateProvider:
    route_key = "openrouter-private"

    def __init__(
        self,
        session: Session,
        *,
        api_key: str,
        approved_providers: list[str],
        transport: OpenRouterTransport,
        cooldown_seconds: int = 60,
    ) -> None:
        if not api_key or not approved_providers:
            raise AppError(
                "AI_PRIVATE_CONFIGURATION_INVALID",
                "Private AI processing is not configured.",
                503,
                retryable=True,
            )
        self.session = session
        self.api_key = api_key
        self.approved_providers = list(dict.fromkeys(approved_providers))
        self.transport = transport
        self.cooldown_seconds = cooldown_seconds

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        response_schema: dict[str, object],
        max_output_tokens: int,
    ) -> ProviderResponse:
        route = self._route()
        cooldown_until = route.cooldown_until
        if cooldown_until is not None and cooldown_until.tzinfo is None:
            cooldown_until = cooldown_until.replace(tzinfo=UTC)
        if not route.enabled or (cooldown_until is not None and cooldown_until > datetime.now(UTC)):
            raise ProviderFailure("AI_PRIVATE_ROUTE_UNAVAILABLE", retryable=True)
        route.total_requests += 1
        route.updated_at = utcnow()
        try:
            text, provider_name, usage = self.transport.generate(
                api_key=self.api_key,
                model=model,
                prompt=prompt,
                response_schema=response_schema,
                max_output_tokens=max_output_tokens,
                approved_providers=self.approved_providers,
            )
        except ProviderFailure as exc:
            route.consecutive_failures += 1
            route.last_error_code = exc.code
            route.health = "COOLDOWN" if exc.retryable else "DEGRADED"
            if exc.retryable:
                route.cooldown_until = utcnow() + timedelta(seconds=self.cooldown_seconds)
            raise
        route.health = "HEALTHY"
        route.cooldown_until = None
        route.consecutive_failures = 0
        route.last_error_code = None
        route.total_tokens += usage.total_tokens
        return ProviderResponse(text, "OPENROUTER", provider_name, model, usage)

    def _route(self) -> AiProviderRoute:
        route = self.session.get(AiProviderRoute, self.route_key)
        if route is None:
            route = AiProviderRoute(route_key=self.route_key, provider="OPENROUTER")
            self.session.add(route)
            self.session.flush()
        return route
