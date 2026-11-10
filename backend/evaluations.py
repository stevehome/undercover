"""Evaluations: a run on a labelled set, working copies of its claims."""

from typing import Any

from sqlalchemy import insert, select

from backend import db, runs, tables
from backend.statuses import ClaimStatus, RunKind

EVALUATION_SET = "evaluation"
HELD_OUT_SET = "held_out"


def copy_id(run_id: int, source_claim_id: str) -> str:
    """Return the id of a run's copy of a claim, such as EVAL-7-CLM-1203."""
    return f"EVAL-{run_id}-{source_claim_id}"


def start_evaluation(
    eval_set: str, tiny: bool, concurrency: int, model: str, reasoning_effort: str
) -> dict[str, Any]:
    """Start an evaluation on a set (all of it, or its `tiny` claims).

    The set's claims are copied under new ids, as waiting, so that the queue and
    the agent's work on it never meet.
    """
    key = tables.answer_key.c
    source = tables.claims if eval_set == EVALUATION_SET else tables.held_out_claims
    with db.connection() as conn:
        wanted = select(key.claim_id).where(key.eval_set == eval_set)
        if tiny:
            wanted = wanted.where(key.tiny.is_(True))
        source_ids = [id_ for (id_,) in conn.execute(wanted.order_by(key.claim_id))]
        run_id = runs.insert_run(
            conn,
            kind=RunKind.EVALUATION,
            concurrency=concurrency,
            eval_set=eval_set,
            tiny=tiny,
            model=model,
            reasoning_effort=reasoning_effort,
        )
        content = conn.execute(
            select(*[source.c[column.name] for column in tables.CONTENT_COLUMNS])
            .where(source.c.claim_id.in_(source_ids))
            .order_by(source.c.claim_id)
        )
        copies = [
            {
                **row._mapping,
                "claim_id": copy_id(run_id, row._mapping["claim_id"]),
                "status": ClaimStatus.WAITING,
                "evaluation_run_id": run_id,
            }
            for row in content
        ]
        if copies:
            conn.execute(insert(tables.claims), copies)
        runs.insert_run_claims(
            conn, run_id, [(copy_id(run_id, id_), id_) for id_ in source_ids]
        )
    return runs.get_run(run_id)
