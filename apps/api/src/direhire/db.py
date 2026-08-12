from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from direhire.config import get_settings, sqlalchemy_database_url


class Base(DeclarativeBase):
    pass


settings = get_settings()
database_url = settings.database_url
if settings.database_url_parameter:
    import boto3

    response = boto3.client("ssm").get_parameter(
        Name=settings.database_url_parameter, WithDecryption=True
    )
    database_url = str(response["Parameter"]["Value"])
database_url = sqlalchemy_database_url(database_url)
engine_options: dict[str, object] = {"pool_pre_ping": True}
if database_url.startswith("postgresql+"):
    engine_options.update(pool_size=3, max_overflow=2)
engine = create_engine(database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
