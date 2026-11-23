import pytest

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


def test_on_lambda_one_connection_is_kept_and_checked(made, monkeypatch):
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "undercover")

    db.make_engine(POSTGRES)

    assert made["pool_size"] == 1
    assert made["max_overflow"] == 0
    assert made["pool_pre_ping"] is True
    assert made["connect_args"] == {"prepare_threshold": None}


@pytest.mark.parametrize("on_lambda", [True, False])
def test_postgres_tables_are_named_with_their_schema(made, monkeypatch, on_lambda):
    if on_lambda:
        monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "undercover")
    else:
        monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)

    db.make_engine(POSTGRES)

    assert made["execution_options"] == {"schema_translate_map": {None: "undercover"}}


def test_elsewhere_the_pool_is_as_it_was(made, monkeypatch):
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)

    db.make_engine(POSTGRES)

    assert made["pool_size"] == db.CONNECTIONS_PER_PROCESS
