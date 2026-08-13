from typing import Literal
from urllib.parse import parse_qs, urlparse

from direhire.auth.oauth import AuthorizationFlow, CognitoIdentity, get_cognito_client
from direhire.db import get_session
from direhire.main import app
from direhire.models import AuthSession, User
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker


class FakeCognitoClient:
    def begin_authorization(
        self, *, screen: Literal["login", "signup"] = "login"
    ) -> AuthorizationFlow:
        return AuthorizationFlow(
            authorization_url=(
                f"https://login.example.invalid/{screen}?"
                "response_type=code&code_challenge=challenge&code_challenge_method=S256"
            ),
            state="expected-state",
            nonce="expected-nonce",
            code_verifier="expected-verifier",
        )

    def complete_authorization(
        self, *, code: str, code_verifier: str, nonce: str
    ) -> CognitoIdentity:
        assert code == "authorization-code"
        assert code_verifier == "expected-verifier"
        assert nonce == "expected-nonce"
        return CognitoIdentity(
            subject="cognito-subject-123",
            email="casey@example.invalid",
            email_verified=True,
            access_token="access-token",
        )

    def begin_mfa_setup(self, access_token: str) -> str:
        assert access_token == "access-token"
        return "ABCDEFGHIJKLMNOP"

    def complete_mfa_setup(self, access_token: str, code: str) -> None:
        assert access_token == "access-token"
        assert code == "123456"


def test_login_starts_pkce_and_callback_issues_opaque_session(
    session_factory: sessionmaker[Session],
) -> None:
    def override_session():  # type: ignore[no-untyped-def]
        with session_factory() as database:
            yield database

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_cognito_client] = FakeCognitoClient
    try:
        with TestClient(app, follow_redirects=False) as client:
            login = client.get("/api/v1/auth/login")
            assert login.status_code == 307
            query = parse_qs(urlparse(login.headers["location"]).query)
            assert query["response_type"] == ["code"]
            assert query["code_challenge_method"] == ["S256"]
            assert client.cookies.get("direhire_oauth_state") == "expected-state"

            callback = client.get(
                "/api/v1/auth/callback",
                params={"code": "authorization-code", "state": "expected-state"},
            )
            assert callback.status_code == 303
            assert callback.headers["location"] == "http://localhost:3000/dashboard"
            raw_session_token = client.cookies.get("direhire_session")
            assert raw_session_token
            assert client.cookies.get("direhire_oauth_state") is None

        with session_factory() as database:
            user = database.scalar(select(User))
            auth_session = database.scalar(select(AuthSession))
            assert user is not None
            assert user.cognito_subject == "cognito-subject-123"
            assert user.email == "casey@example.invalid"
            assert auth_session is not None
            assert auth_session.token_hash != raw_session_token
    finally:
        app.dependency_overrides.clear()


def test_signup_starts_pkce_on_cognito_signup_page(
    session_factory: sessionmaker[Session],
) -> None:
    def override_session():  # type: ignore[no-untyped-def]
        with session_factory() as database:
            yield database

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_cognito_client] = FakeCognitoClient
    try:
        with TestClient(app, follow_redirects=False) as client:
            response = client.get("/api/v1/auth/signup")
            assert response.status_code == 307
            assert urlparse(response.headers["location"]).path == "/signup"
            assert client.cookies.get("direhire_oauth_state") == "expected-state"
            assert client.cookies.get("direhire_pkce_verifier") == "expected-verifier"
    finally:
        app.dependency_overrides.clear()


def test_callback_rejects_state_mismatch(session_factory: sessionmaker[Session]) -> None:
    def override_session():  # type: ignore[no-untyped-def]
        with session_factory() as database:
            yield database

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_cognito_client] = FakeCognitoClient
    try:
        with TestClient(app, follow_redirects=False) as client:
            client.get("/api/v1/auth/login")
            response = client.get(
                "/api/v1/auth/callback",
                params={"code": "authorization-code", "state": "attacker-state"},
            )
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "AUTH_STATE_INVALID"
    finally:
        app.dependency_overrides.clear()


def test_user_can_enable_optional_totp_and_session_is_revoked(
    session_factory: sessionmaker[Session],
) -> None:
    def override_session():  # type: ignore[no-untyped-def]
        with session_factory() as database:
            yield database

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_cognito_client] = FakeCognitoClient
    try:
        with TestClient(app, follow_redirects=False) as client:
            client.get("/api/v1/auth/login")
            client.get(
                "/api/v1/auth/callback",
                params={"code": "authorization-code", "state": "expected-state"},
            )
            csrf = client.cookies.get("direhire_csrf")
            assert csrf

            setup = client.get("/api/v1/auth/mfa/setup")
            assert setup.status_code == 307
            callback = client.get(
                "/api/v1/auth/callback",
                params={"code": "authorization-code", "state": "expected-state"},
            )
            assert callback.status_code == 303
            assert callback.headers["location"].endswith("/settings/?mfa=setup")
            details = client.get("/api/v1/auth/mfa/setup-details")
            assert details.status_code == 200
            assert details.json()["secret_code"] == "ABCDEFGHIJKLMNOP"

            verified = client.post(
                "/api/v1/auth/mfa/verify",
                json={"code": "123456"},
                headers={"X-CSRF-Token": csrf},
            )
            assert verified.status_code == 204
            assert client.get("/api/v1/auth/session").status_code == 401

        with session_factory() as database:
            user = database.scalar(select(User))
            assert user is not None
            assert user.mfa_enabled is True
            assert user.security_version == 2
    finally:
        app.dependency_overrides.clear()
