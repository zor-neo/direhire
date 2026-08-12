from direhire.config import sqlalchemy_database_url


def test_standard_postgresql_urls_use_installed_psycopg_driver() -> None:
    assert (
        sqlalchemy_database_url("postgresql://user:pass@db.example/app?sslmode=require")
        == "postgresql+psycopg://user:pass@db.example/app?sslmode=require"
    )
    assert (
        sqlalchemy_database_url("postgres://user:pass@db.example/app?sslmode=require")
        == "postgresql+psycopg://user:pass@db.example/app?sslmode=require"
    )


def test_explicit_sqlalchemy_driver_is_preserved() -> None:
    value = "postgresql+psycopg://user:pass@db.example/app?sslmode=require"
    assert sqlalchemy_database_url(value) == value
