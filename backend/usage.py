"""What a claim cost to work: the model calls and the time spent, by run.

A row with no run belongs to no run's totals.
"""

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, insert, select

from backend import db, money, tables
from backend.money import Cost


class ModelCall(BaseModel):
    """One model call's model, tokens and cost, and the run it belongs to."""

    run_id: int | None
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: Cost


def record_model_call(claim_id: str, call: ModelCall) -> dict[str, Any]:
    """Record one model call's tokens and cost."""
    row = call.model_dump(exclude={"cost"})
    cost_nanos = money.to_nanos(call.cost)
    with db.connection() as conn:
        conn.execute(
            insert(tables.model_calls).values(
                **row, claim_id=claim_id, cost_nanos=cost_nanos
            )
        )
    return {"claim_id": claim_id, "run_id": call.run_id}


def record_work_segment(
    claim_id: str, run_id: int | None, started_on: str, finished_on: str
) -> dict[str, Any]:
    """Record one stretch of the agent working on a claim."""
    with db.connection() as conn:
        conn.execute(
            insert(tables.work_segments).values(
                claim_id=claim_id,
                run_id=run_id,
                started_on=started_on,
                finished_on=finished_on,
            )
        )
    return {"claim_id": claim_id, "run_id": run_id}


def _milliseconds(started_on: str, finished_on: str) -> int:
    span = datetime.fromisoformat(finished_on) - datetime.fromisoformat(started_on)
    return span // timedelta(milliseconds=1)


def run_totals(run_id: int) -> dict[str, Any]:
    """Sum a run's model calls and working time, failed attempts included."""
    calls = tables.model_calls
    with db.connection() as conn:
        tokens = conn.execute(
            select(
                func.count(),
                func.coalesce(func.sum(calls.c.total_tokens), 0),
                func.coalesce(func.sum(calls.c.cost_nanos), 0),
            ).where(calls.c.run_id == run_id)
        ).one()
        segments = conn.execute(
            select(
                tables.work_segments.c.started_on, tables.work_segments.c.finished_on
            ).where(tables.work_segments.c.run_id == run_id)
        )
        work_ms = sum(_milliseconds(*row) for row in segments)
    return {
        "model_calls": tokens[0],
        "total_tokens": tokens[1],
        "cost": money.from_nanos(tokens[2]),
        "work_ms": work_ms,
    }


def claim_totals(run_id: int) -> dict[str, dict[str, Any]]:
    """Sum each claim's model cost and working time within a run."""
    calls = tables.model_calls
    segments = tables.work_segments
    with db.connection() as conn:
        costs = conn.execute(
            select(calls.c.claim_id, func.sum(calls.c.cost_nanos))
            .where(calls.c.run_id == run_id)
            .group_by(calls.c.claim_id)
        )
        totals: dict[str, dict[str, Any]] = {}
        for claim_id, nanos in costs:
            totals.setdefault(claim_id, {"cost": 0, "work_ms": 0})["cost"] = nanos
        times = conn.execute(
            select(
                segments.c.claim_id, segments.c.started_on, segments.c.finished_on
            ).where(segments.c.run_id == run_id)
        )
        for claim_id, started_on, finished_on in times:
            totals.setdefault(claim_id, {"cost": 0, "work_ms": 0})["work_ms"] += (
                _milliseconds(started_on, finished_on)
            )
    return {
        claim_id: {"cost": money.from_nanos(total["cost"]), "work_ms": total["work_ms"]}
        for claim_id, total in totals.items()
    }
