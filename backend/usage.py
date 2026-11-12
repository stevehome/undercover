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


def totals(run_ids: list[int]) -> dict[int, dict[str, Any]]:
    """Sum each run's and each claim's model calls and working time, in two queries.

    Failed attempts are included. A run with no work has zero totals.
    """
    calls, segments = tables.model_calls.c, tables.work_segments.c
    found: dict[int, dict[str, Any]] = {
        run_id: {"model_calls": 0, "total_tokens": 0, "cost": 0, "work_ms": 0}
        | {"claims": {}}
        for run_id in run_ids
    }
    with db.connection() as conn:
        costs = conn.execute(
            select(
                calls.run_id,
                calls.claim_id,
                func.count(),
                func.sum(calls.total_tokens),
                func.sum(calls.cost_nanos),
            )
            .where(calls.run_id.in_(run_ids))
            .group_by(calls.run_id, calls.claim_id)
        )
        for run_id, claim_id, count, tokens, nanos in costs:
            run = found[run_id]
            run["model_calls"] += count
            run["total_tokens"] += int(tokens)
            run["cost"] += nanos
            run["claims"].setdefault(claim_id, {"cost": 0, "work_ms": 0})["cost"] = (
                nanos
            )
        times = conn.execute(
            select(
                segments.run_id,
                segments.claim_id,
                segments.started_on,
                segments.finished_on,
            ).where(segments.run_id.in_(run_ids))
        )
        for run_id, claim_id, started_on, finished_on in times:
            run = found[run_id]
            milliseconds = _milliseconds(started_on, finished_on)
            run["work_ms"] += milliseconds
            run["claims"].setdefault(claim_id, {"cost": 0, "work_ms": 0})[
                "work_ms"
            ] += milliseconds
    return {
        run_id: {
            **run,
            "cost": money.from_nanos(run["cost"]),
            "claims": {
                claim_id: {**claim, "cost": money.from_nanos(claim["cost"])}
                for claim_id, claim in run["claims"].items()
            },
        }
        for run_id, run in found.items()
    }


def run_totals(run_id: int) -> dict[str, Any]:
    """Sum a run's model calls and working time, failed attempts included."""
    return {k: v for k, v in totals([run_id])[run_id].items() if k != "claims"}
