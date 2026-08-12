import os
from collections.abc import Generator
from uuid import UUID

os.environ.setdefault("DIREHIRE_ENVIRONMENT", "test")
os.environ.setdefault("DIREHIRE_DATABASE_URL", "sqlite+pysqlite:///./.pytest-bootstrap.db")

import pytest
from direhire.auth import CurrentUser, current_user
from direhire.db import Base, get_session
from direhire.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

USER_A = UUID("11111111-1111-4111-8111-111111111111")
USER_B = UUID("22222222-2222-4222-8222-222222222222")


@pytest.fixture
def session_factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:
    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_A)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
