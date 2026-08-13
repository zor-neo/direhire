from datetime import UTC, datetime, timedelta

import pytest
from direhire.auth.session_service import SessionService, token_hash
from direhire.config import Settings
from direhire.db import get_session
from direhire.errors import AppError
from direhire.main import app
from direhire.models import AuthSession, User
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A


def test_production_configuration_rejects_insecure_auth_database_and_cors() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            database_url="postgresql+psycopg://db.example/direhire",
            cors_origins=["*"],
            allow_insecure_dev_auth=True,
        )


def test_session_stores_only_hashes_and_authenticates(
    session_factory: sessionmaker[Session],
) -> None:
    now = datetime(2026, 8, 12, 8, 0, tzinfo=UTC)
    settings = make_settings()
    with session_factory() as database:
        user = add_user(database)
        issued = SessionService(database, settings).issue(user, now=now)
        stored = database.scalar(select(AuthSession))
        assert stored is not None
        assert stored.token_hash == token_hash(issued.token)
        assert issued.token not in stored.token_hash
        assert stored.csrf_token_hash == token_hash(issued.csrf_token)

        identity = SessionService(database, settings).authenticate(
            issued.token,
            csrf_token=issued.csrf_token,
            require_csrf=True,
            now=now + timedelta(minutes=1),
        )
        assert identity.user_id == USER_A
        assert identity.role == "USER"


def test_last_seen_updates_only_after_bounded_interval(
    session_factory: sessionmaker[Session],
) -> None:
    now = datetime(2026, 8, 12, 8, 0, tzinfo=UTC)
    settings = make_settings(session_last_seen_interval_seconds=300)
    with session_factory() as database:
        service = SessionService(database, settings)
        issued = service.issue(add_user(database), now=now)
        service.authenticate(issued.token, now=now + timedelta(seconds=299))
        stored = database.scalar(select(AuthSession))
        assert stored is not None
        assert stored.last_seen_at.replace(tzinfo=UTC) == now

        service.authenticate(issued.token, now=now + timedelta(seconds=300))
        assert stored.last_seen_at.replace(tzinfo=UTC) == now + timedelta(seconds=300)


def test_expired_revoked_and_security_version_sessions_are_rejected(
    session_factory: sessionmaker[Session],
) -> None:
    now = datetime(2026, 8, 12, 8, 0, tzinfo=UTC)
    settings = make_settings(session_lifetime_seconds=60)
    with session_factory() as database:
        user = add_user(database)
        service = SessionService(database, settings)

        expired = service.issue(user, now=now)
        with pytest.raises(AppError, match="Please sign in"):
            service.authenticate(expired.token, now=now + timedelta(seconds=61))

        revoked = service.issue(user, now=now)
        identity = service.authenticate(revoked.token, now=now)
        service.revoke(identity.session_id, now=now)
        with pytest.raises(AppError, match="Please sign in"):
            service.authenticate(revoked.token, now=now)

        stale = service.issue(user, now=now)
        user.security_version += 1
        database.commit()
        with pytest.raises(AppError, match="Please sign in"):
            service.authenticate(stale.token, now=now)


def test_privileged_session_requires_mfa(session_factory: sessionmaker[Session]) -> None:
    now = datetime(2026, 8, 12, 8, 0, tzinfo=UTC)
    with session_factory() as database:
        user = add_user(database, role="ADMIN", mfa_enabled=False)
        service = SessionService(database, make_settings())
        issued = service.issue(user, now=now)
        with pytest.raises(AppError) as error:
            service.authenticate(issued.token, now=now)
        assert error.value.code == "MFA_REQUIRED"


def test_cookie_auth_requires_csrf_for_mutation_and_not_for_read(
    session_factory: sessionmaker[Session],
) -> None:
    settings = make_settings()

    def override_session():  # type: ignore[no-untyped-def]
        with session_factory() as database:
            yield database

    with session_factory() as database:
        issued = SessionService(database, settings).issue(add_user(database))

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            client.cookies.set(settings.session_cookie_name, issued.token)
            client.cookies.set(settings.csrf_cookie_name, issued.csrf_token)
            assert client.get("/api/v1/watches").status_code == 200
            payload = {"name": "Security roles", "target_terms": ["IAM"]}
            assert client.post("/api/v1/watches", json=payload).status_code == 403
            response = client.post(
                "/api/v1/watches",
                json=payload,
                headers={"X-CSRF-Token": issued.csrf_token},
            )
            assert response.status_code == 201
            logout = client.delete(
                "/api/v1/auth/session",
                headers={"X-CSRF-Token": issued.csrf_token},
            )
            assert logout.status_code == 204
            assert client.get("/api/v1/watches").status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_authenticated_client_can_bootstrap_cross_origin_csrf_token(
    session_factory: sessionmaker[Session],
) -> None:
    settings = make_settings()

    def override_session():  # type: ignore[no-untyped-def]
        with session_factory() as database:
            yield database

    with session_factory() as database:
        issued = SessionService(database, settings).issue(add_user(database))

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            client.cookies.set(settings.session_cookie_name, issued.token)
            client.cookies.set(settings.csrf_cookie_name, issued.csrf_token)
            response = client.get("/api/v1/auth/csrf-token")
            assert response.status_code == 200
            assert response.json() == {"csrf_token": issued.csrf_token}
            assert response.headers["cache-control"] == "no-store"
    finally:
        app.dependency_overrides.clear()


def test_authenticated_client_can_bootstrap_product_session(
    session_factory: sessionmaker[Session],
) -> None:
    settings = make_settings()

    def override_session():  # type: ignore[no-untyped-def]
        with session_factory() as database:
            yield database

    with session_factory() as database:
        issued = SessionService(database, settings).issue(add_user(database))

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            client.cookies.set(settings.session_cookie_name, issued.token)
            response = client.get("/api/v1/auth/session")
            assert response.status_code == 200
            assert response.json() == {"role": "USER", "plan": "FREE"}
            assert response.headers["cache-control"] == "no-store"
    finally:
        app.dependency_overrides.clear()


def test_product_session_bootstrap_requires_authentication(
    session_factory: sessionmaker[Session],
) -> None:
    def override_session():  # type: ignore[no-untyped-def]
        with session_factory() as database:
            yield database

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/auth/session")
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    finally:
        app.dependency_overrides.clear()


def test_platform_catalog_requires_authentication(
    session_factory: sessionmaker[Session],
) -> None:
    def override_session():  # type: ignore[no-untyped-def]
        with session_factory() as database:
            yield database

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/watches/platforms")
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    finally:
        app.dependency_overrides.clear()


def test_csrf_bootstrap_requires_an_authenticated_session(
    session_factory: sessionmaker[Session],
) -> None:
    def override_session():  # type: ignore[no-untyped-def]
        with session_factory() as database:
            yield database

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/auth/csrf-token")
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    finally:
        app.dependency_overrides.clear()


def add_user(
    database: Session,
    *,
    role: str = "USER",
    mfa_enabled: bool = False,
) -> User:
    user = User(
        id=str(USER_A),
        cognito_subject=f"synthetic-{role.casefold()}",
        email="alex@example.invalid",
        role=role,
        mfa_enabled=mfa_enabled,
    )
    database.add(user)
    database.commit()
    return user


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "database_url": "sqlite+pysqlite:///:memory:",
        "cors_origins": ["http://localhost:3000"],
        "allow_insecure_dev_auth": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)
