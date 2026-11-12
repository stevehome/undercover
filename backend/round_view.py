"""A round as the dashboard reads it: its records with its proposals and its cost."""

from typing import Any

from sqlalchemy import select

from backend import (
    db,
    proposals,
    reference,
    rounds,
    spending,
    tables,
    version_scores,
    versions,
)


def _views(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rounds with their proposals and cost, in a fixed number of queries."""
    ids = [row["round_id"] for row in rows]
    names = {h["handler_id"]: h["name"] for h in reference.handlers()}
    cost, proposed = spending.spent_by(ids), proposals.for_rounds(ids)
    return [
        {
            **row,
            "started_by_name": names[row["started_by"]],
            "cost": cost[row["round_id"]],
            "spending_limit": spending.limit(row["settings"]),
            "proposals": proposed[row["round_id"]],
        }
        for row in rows
    ]


def get_round(round_id: int) -> dict[str, Any]:
    """Return a round with its proposals, in order, and what it has cost."""
    return _views([rounds.get_row(round_id)])[0]


def list_rounds() -> list[dict[str, Any]]:
    """List the rounds, newest first."""
    column = tables.rounds.c.round_id
    with db.connection() as conn:
        found = conn.execute(select(tables.rounds).order_by(column.desc()))
        return _views([dict(row._mapping) for row in found])


def list_configurations() -> list[dict[str, Any]]:
    """List every configuration version with its scores on the held-out set."""
    rows = versions.list_configurations()
    scores = version_scores.scores_for([row["version"] for row in rows], "held_out")
    return [{**row, "held_out": scores[row["version"]]} for row in rows]
