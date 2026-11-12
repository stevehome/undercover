"""Versions of the claim agent's configuration and of the improver's recipe.

A version is a record. The current one is the highest the rounds have kept,
worked out from the rows, so it can't drift from a separate pointer.
"""

from typing import Any

from sqlalchemy import Connection, Table, func, insert, select

from backend import db, diffs, tables
from backend.errors import NotFound
from backend.statuses import Verdict


def _rows(table: Table) -> list[dict[str, Any]]:
    with db.connection() as conn:
        found = conn.execute(select(table).order_by(table.c.version))
        return [dict(row._mapping) for row in found]


def _get(table: Table, version: int) -> dict[str, Any]:
    found = [row for row in _rows(table) if row["version"] == version]
    if not found:
        raise NotFound(f"No {table.name.removesuffix('s')} version {version}")
    return found[0]


def _current(table: Table) -> dict[str, Any]:
    return [row for row in _rows(table) if row["verdict"] == Verdict.KEPT][-1]


def current_configuration() -> dict[str, Any]:
    """Return the highest configuration version a round has kept."""
    return _current(tables.configurations)


def get_configuration(version: int) -> dict[str, Any]:
    """Return one configuration version, or raise NotFound."""
    return _get(tables.configurations, version)


def list_configurations() -> list[dict[str, Any]]:
    """List every configuration version, oldest first."""
    return _rows(tables.configurations)


def current_recipe() -> dict[str, Any]:
    """Return the highest recipe version a round has kept."""
    return _current(tables.recipes)


def list_recipes() -> list[dict[str, Any]]:
    """List every recipe version, oldest first."""
    return _rows(tables.recipes)


def configuration_for_agent(version: int) -> dict[str, Any]:
    """Return what the claim agent needs of a version: no scores, no reasons."""
    row = get_configuration(version)
    return {
        "version": row["version"],
        "instructions": row["instructions"],
        "model": row["model"],
        "reasoning_effort": row["reasoning_effort"],
    }


def configuration_diff(version: int) -> dict[str, Any]:
    """Return what a configuration version changed from the one before it."""
    new = get_configuration(version)
    old = _get(tables.configurations, version - 1) if version > 1 else None
    return {
        "version": version,
        "from_version": None if old is None else old["version"],
        "lines": diffs.diff_lines(
            "" if old is None else old["instructions"], new["instructions"]
        ),
        "model_before": None if old is None else old["model"],
        "model_after": new["model"],
        "reasoning_effort_before": None if old is None else old["reasoning_effort"],
        "reasoning_effort_after": new["reasoning_effort"],
    }


def recipe_diff(version: int) -> dict[str, Any]:
    """Return what a recipe version changed from the one before it."""
    new = _get(tables.recipes, version)
    old = _get(tables.recipes, version - 1) if version > 1 else None
    return {
        "version": version,
        "from_version": None if old is None else old["version"],
        "lines": diffs.diff_lines("" if old is None else old["text"], new["text"]),
    }


def add_version(conn: Connection, table: Table, **values: Any) -> int:
    """Add the next version of a table in the caller's transaction; return it."""
    version = conn.execute(select(func.max(table.c.version))).scalar_one() + 1
    conn.execute(insert(table).values(version=version, created_on=db.now(), **values))
    return version
