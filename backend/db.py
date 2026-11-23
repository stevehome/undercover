"""The database: one way to connect, on SQLite or Postgres, and to seed it."""

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock

from sqlalchemy import Connection, Engine, create_engine, func, insert, select, text

from backend import money, seed_data, tables

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "undercover.db"
SCHEMA = os.environ.get("UNDERCOVER_SCHEMA", "undercover")
CONNECTIONS_PER_PROCESS = 4
WAIT_FOR_CONNECTION_SECONDS = 600
RECYCLE_CONNECTION_SECONDS = 300


def db_path() -> Path:
    """Return the SQLite file to use, from DATABASE_PATH or the default."""
    return Path(os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH))


def database_url() -> str:
    """Return the database to use: Supabase if DATABASE_URL is set, else SQLite."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return f"sqlite:///{db_path()}"


_lock = Lock()
_engines: dict[str, Engine] = {}


def on_lambda() -> bool:
    """Say whether this is AWS Lambda, which sets the name of the function."""
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


def make_engine(url: str) -> Engine:
    """Make an engine; Postgres keeps our tables in their own schema.

    The tables are named with their schema in each statement, as Supabase's
    transaction pooler can't be trusted to keep a connection's search path.
    On Lambda each instance handles one request at a time, so it keeps one
    connection for the next request, checked as it is taken, rather than making
    a new one, which costs several trips to the database; and no prepared
    statements, which that pooler can't keep.
    """
    json_options = {
        "json_serializer": lambda value: json.dumps(value, default=str),
        "json_deserializer": lambda text: money.convert(json.loads(text)),
    }
    if url.startswith("sqlite"):
        return create_engine(url, **json_options)
    in_schema = {"schema_translate_map": {None: SCHEMA}}
    if on_lambda():
        return create_engine(
            url,
            **json_options,
            pool_size=1,
            max_overflow=0,
            pool_pre_ping=True,
            pool_recycle=RECYCLE_CONNECTION_SECONDS,
            connect_args={"prepare_threshold": None},
            execution_options=in_schema,
        )
    return create_engine(
        url,
        **json_options,
        pool_size=CONNECTIONS_PER_PROCESS,
        max_overflow=0,
        pool_timeout=WAIT_FOR_CONNECTION_SECONDS,
        pool_pre_ping=True,
        pool_recycle=RECYCLE_CONNECTION_SECONDS,
        execution_options=in_schema,
    )


def engine(url: str) -> Engine:
    """Return the engine for a database, made once even when requests race for it."""
    with _lock:
        if url not in _engines:
            made = make_engine(url)
            _engines[url] = made if on_lambda() else _prepare(made, url)
        return _engines[url]


def forget_engines() -> None:
    """Forget every engine, so the next use makes one again."""
    with _lock:
        _engines.clear()


def _prepare(made: Engine, url: str) -> Engine:
    """Create a database's schema and tables, and seed them if they are empty.

    On Lambda it isn't called: the database is made and seeded from a laptop.
    """
    if not url.startswith("sqlite"):
        with made.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
    tables.metadata.create_all(made)
    with made.begin() as conn:
        if (
            conn.execute(select(func.count()).select_from(tables.claims)).scalar_one()
            == 0
        ):
            for table, rows in seed_data.records().items():
                conn.execute(insert(table), rows)
    return made


@contextmanager
def connection() -> Iterator[Connection]:
    """Open a connection that commits on success, rolls back on error, and closes."""
    with engine(database_url()).begin() as conn:
        yield conn


def now(plus_seconds: int = 0) -> str:
    """Return the UTC time, now or some seconds ahead, as an ISO 8601 string."""
    return (datetime.now(UTC) + timedelta(seconds=plus_seconds)).isoformat()
