import pytest
from sqlalchemy.pool import NullPool

from backend import db

POSTGRES = "postgresql+psycopg://user:password@localhost/postgres"


@pytest.fixture
def made(monkeypatch):
    """The options `make_engine` gives SQLAlchemy, with no connection made."""
    options = {}

    def create_engine(url, **kwargs):
        options.update(kwargs)

    monkeypatch.setattr(db, "create_engine", create_engine)
    return options


def test_on_lambda_there_is_no_pool_and_no_prepared_statements(made, monkeypatch):
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "undercover")

    db.make_engine(POSTGRES)

    assert made["poolclass"] is NullPool
    assert made["connect_args"]["prepare_threshold"] is None
    assert "search_path=undercover" in made["connect_args"]["options"]


def test_elsewhere_the_pool_is_as_it_was(made, monkeypatch):
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)

    db.make_engine(POSTGRES)

    assert made["pool_size"] == db.CONNECTIONS_PER_PROCESS
    assert "poolclass" not in made
    assert "prepare_threshold" not in made["connect_args"]
