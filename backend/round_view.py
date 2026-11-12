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


def get_round(round_id: int) -> dict[str, Any]:
    """Return a round with its proposals, in order, and what it has cost."""
    row = rounds.get_row(round_id)
    columns = tables.proposals.c
    with db.connection() as conn:
        found = conn.execute(
            select(columns.proposal_id)
            .where(columns.round_id == round_id)
            .order_by(columns.proposal_id)
        )
        proposal_ids = [proposal_id for (proposal_id,) in found]
    names = {h["handler_id"]: h["name"] for h in reference.handlers()}
    return {
        **row,
        "started_by_name": names[row["started_by"]],
        "cost": spending.spent(round_id),
        "spending_limit": spending.limit(row["settings"]),
        "proposals": [proposals.get_proposal(p) for p in proposal_ids],
    }


def list_rounds() -> list[dict[str, Any]]:
    """List the rounds, newest first."""
    column = tables.rounds.c.round_id
    with db.connection() as conn:
        ids = [r for (r,) in conn.execute(select(column).order_by(column.desc()))]
    return [get_round(round_id) for round_id in ids]


def list_configurations() -> list[dict[str, Any]]:
    """List every configuration version with its scores on the held-out set."""
    return [
        {**row, "held_out": version_scores.scores_on(row["version"], "held_out")}
        for row in versions.list_configurations()
    ]
