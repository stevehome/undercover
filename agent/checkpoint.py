"""The agent's saved progress: the one module that talks to Postgres.

LangGraph saves a claim's state here after every step, in the same Supabase
database as the backend, in the `undercover` schema. Claims worked at once
share the process's few connections and wait for one rather than fail.
"""

import os
from functools import lru_cache
from threading import Lock
from typing import Any

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

SCHEMA = "undercover"
CONNECTIONS_PER_PROCESS = 4
WAIT_FOR_CONNECTION_SECONDS = 600


_creating = Lock()


def saver() -> PostgresSaver:
    """Return a checkpointer of its own on this process's pool of connections.

    A saver holds a lock around every read and write, so claims worked in
    parallel each need one. The pool is made once even when claims race for it.
    """
    with _creating:
        pool = _make_pool()
    return PostgresSaver(pool)  # pyright: ignore[reportArgumentType]


def forget() -> None:
    """Forget this process's pool, so the next use makes one again."""
    _make_pool.cache_clear()


@lru_cache
def _make_pool() -> ConnectionPool[Any]:
    pool = ConnectionPool(
        os.environ["DATABASE_URL"],
        min_size=CONNECTIONS_PER_PROCESS,
        max_size=CONNECTIONS_PER_PROCESS,
        timeout=WAIT_FOR_CONNECTION_SECONDS,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
            "options": f"-c search_path={SCHEMA}",
        },
        open=False,
    )
    pool.open()
    with pool.connection() as connection:
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    PostgresSaver(pool).setup()  # pyright: ignore[reportArgumentType]
    return pool
