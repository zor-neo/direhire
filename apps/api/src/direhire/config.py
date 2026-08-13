from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def sqlalchemy_database_url(value: str) -> str:
    """Select the installed psycopg v3 driver for standard PostgreSQL URLs."""
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DIREHIRE_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://direhire:direhire@localhost:5432/direhire"
    database_url_parameter: str | None = None
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    allow_insecure_dev_auth: bool = False
    session_cookie_name: str = "direhire_session"
    csrf_cookie_name: str = "direhire_csrf"
    session_lifetime_seconds: int = 60 * 60 * 24 * 7
    session_last_seen_interval_seconds: int = 60 * 5
    cognito_domain: str | None = None
    cognito_user_pool_id: str | None = None
    cognito_client_id: str | None = None
    cognito_redirect_uri: str | None = None
    frontend_post_login_url: str = "http://localhost:3000"
    discovery_queue_url: str | None = None
    queue_routes: dict[str, str] = Field(default_factory=dict)
    public_fetch_max_bytes: int = 2_000_000
    public_fetch_cache_seconds: int = 300
    public_fetch_lease_seconds: int = 120
    usajobs_enabled: bool = False
    usajobs_api_key_parameter: str = "/prod/sources/usajobs/api-key"
    usajobs_user_agent_parameter: str = "/prod/sources/usajobs/user-agent"
    ai_enabled: bool = True
    gemini_project_a_parameter: str = "/prod/ai/gemini/public/project-a/api-key"
    gemini_project_b_parameter: str = "/prod/ai/gemini/public/project-b/api-key"
    gemini_project_c_parameter: str = "/prod/ai/gemini/public/project-c/api-key"
    openrouter_private_parameter: str = "/prod/ai/openrouter/private/api-key"
    openrouter_private_providers: list[str] = Field(default_factory=lambda: ["anthropic"])
    telegram_enabled: bool = True
    whatsapp_enabled: bool = True
    telegram_token_parameter: str = "/prod/notifications/telegram/bot-token"
    whatsapp_token_parameter: str = "/prod/notifications/whatsapp/access-token"
    whatsapp_phone_id_parameter: str = "/prod/notifications/whatsapp/phone-number-id"
    whatsapp_graph_version: str = "v23.0"
    private_bucket_name: str = "direhire-private-local"
    private_upload_max_bytes: int = 10_000_000
    private_download_url_seconds: int = 300

    @model_validator(mode="after")
    def validate_security_boundaries(self) -> "Settings":
        if self.environment != "production":
            return self
        if self.allow_insecure_dev_auth:
            raise ValueError("insecure development authentication is forbidden in production")
        if not self.database_url_parameter and (
            not self.database_url.startswith("postgresql+")
            or "sslmode=require" not in self.database_url
        ):
            raise ValueError("production PostgreSQL connections must explicitly require TLS")
        if not self.cors_origins or any(
            origin == "*" or not origin.startswith("https://") for origin in self.cors_origins
        ):
            raise ValueError("production CORS origins must be explicit HTTPS origins")
        if not all(
            (
                self.cognito_domain,
                self.cognito_user_pool_id,
                self.cognito_client_id,
                self.cognito_redirect_uri,
            )
        ):
            raise ValueError("production Cognito configuration is incomplete")
        if not self.frontend_post_login_url.startswith("https://"):
            raise ValueError("production post-login URL must use HTTPS")
        if self.usajobs_enabled and not all(
            (self.usajobs_api_key_parameter, self.usajobs_user_agent_parameter)
        ):
            raise ValueError("USAJOBS credential parameters are incomplete")
        required_events = {
            "watch.discovery.requested",
            "analyze.job.requested",
            "job.analysis.requested",
            "private.ai.requested",
            "watch.query-expansion.requested",
            "notification.digest.requested",
            "private.document.requested",
            "file.scan.requested",
            "privacy.export.requested",
            "privacy.deletion.requested",
        }
        if required_events - self.queue_routes.keys():
            raise ValueError("production queue routing is incomplete")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
