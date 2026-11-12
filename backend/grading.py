"""Grading an evaluation: the judge's grade for each claim's explanation, stored."""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from typing import Any

from sqlalchemy import insert, select

from backend import db, judge, money, tables

logger = logging.getLogger(__name__)

NO_DECISION = judge.Judgement(
    score=Decimal(0),
    letter="F",
    same_grounds=Decimal(0),
    same_section=Decimal(0),
    cost=Decimal(0),
)


def _claims_to_grade(run_id: int) -> list[dict[str, Any]]:
    """The agent's answer beside the handler's reason, for each claim of a run."""
    in_run, claims, key = tables.run_claims.c, tables.claims.c, tables.answer_key.c
    with db.connection() as conn:
        rows = conn.execute(
            select(
                in_run.claim_id,
                claims.decision,
                claims.reason,
                claims.policy_reference,
                key.decision.label("handler_decision"),
                key.reason.label("handler_reason"),
                key.reference.label("handler_reference"),
            )
            .join(tables.claims, claims.claim_id == in_run.claim_id)
            .join(
                tables.runs,
                tables.runs.c.run_id == in_run.run_id,
            )
            .join(
                tables.answer_key,
                (key.eval_set == tables.runs.c.eval_set)
                & (key.claim_id == in_run.source_claim_id),
            )
            .where(in_run.run_id == run_id)
        )
        return [dict(row._mapping) for row in rows]


def _ask(row: dict[str, Any]) -> judge.Judgement | None:
    """Ask the judge about one claim: F with no call if undecided; None if it fails."""
    if row["decision"] is None:
        return NO_DECISION
    handler = {
        "decision": row["handler_decision"],
        "reason": row["handler_reason"],
        "reference": row["handler_reference"],
    }
    agent = {
        "decision": row["decision"],
        "rationale": row["reason"],
        "section": row["policy_reference"],
    }
    try:
        return judge.judge(handler, agent)
    except Exception:
        logger.exception("The judge could not grade %s", row["claim_id"])
        return None


def _grade_row(run_id: int, claim_id: str, judgement: judge.Judgement | None):
    if judgement is None:
        return {
            "run_id": run_id,
            "claim_id": claim_id,
            "graded": False,
            "cost_nanos": 0,
        }
    return {
        "run_id": run_id,
        "claim_id": claim_id,
        "graded": True,
        "score": str(judgement.score),
        "letter": judgement.letter,
        "same_grounds": str(judgement.same_grounds),
        "same_section": str(judgement.same_section),
        "cost_nanos": money.to_nanos(judgement.cost),
    }


def grade_evaluation(run_id: int) -> None:
    """Grade every claim of an evaluation in parallel, and store the grades.

    With MODEL_NAME set the judge isn't called, and the claims stay not graded.
    """
    if os.getenv("MODEL_NAME"):
        return
    rows = _claims_to_grade(run_id)
    if not rows:
        return
    with ThreadPoolExecutor(max_workers=len(rows)) as pool:
        judgements = list(pool.map(_ask, rows))
    with db.connection() as conn:
        conn.execute(
            insert(tables.claim_grades),
            [
                _grade_row(run_id, row["claim_id"], judgement)
                for row, judgement in zip(rows, judgements, strict=True)
            ],
        )


def grades(run_ids: list[int]) -> dict[int, dict[str, dict[str, Any]]]:
    """Return the stored grades of runs by run id, then claim id."""
    columns = tables.claim_grades.c
    found: dict[int, dict[str, dict[str, Any]]] = {run_id: {} for run_id in run_ids}
    with db.connection() as conn:
        for row in conn.execute(
            select(tables.claim_grades).where(columns.run_id.in_(run_ids))
        ):
            found[row.run_id][row.claim_id] = dict(row._mapping)
    return found
