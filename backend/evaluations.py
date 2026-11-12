"""Evaluations: a run on a labelled set, working copies of its claims."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, insert, select

from backend import db, grading, money, runs, scoring, tables, usage, versions
from backend.errors import NotFound
from backend.statuses import ClaimStatus, RunKind

EVALUATION_SET = "evaluation"
HELD_OUT_SET = "held_out"
MATCHED = Decimal("0.5")


def set_size(eval_set: str) -> int:
    """Return how many claims a labelled set has."""
    key = tables.answer_key.c
    with db.connection() as conn:
        return conn.execute(
            select(func.count())
            .select_from(tables.answer_key)
            .where(key.eval_set == eval_set)
        ).scalar_one()


def copy_id(run_id: int, source_claim_id: str) -> str:
    """Return the id of a run's copy of a claim, such as EVAL-7-CLM-1203."""
    return f"EVAL-{run_id}-{source_claim_id}"


def start_evaluation(
    eval_set: str,
    tiny: bool,
    concurrency: int,
    settings: runs.RunSettings,
    in_round: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """Start an evaluation on a set (all of it, or its `tiny` claims).

    The set's claims are copied under new ids, as waiting, so that the queue and
    the agent's work on it never meet. An evaluation in a round is given the round
    and the stretch of the improver's work it belongs to, as (round id, run id).
    """
    round_id, parent_run_id = in_round or (None, None)
    versions.get_configuration(settings.configuration_version)
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
            round_id=round_id,
            parent_run_id=parent_run_id,
            **settings.columns(),
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


def _run_ms(run: dict[str, Any]) -> int | None:
    """Return how long a run took, or None while it is still running."""
    if run["finished_on"] is None:
        return None
    span = datetime.fromisoformat(run["finished_on"]) - datetime.fromisoformat(
        run["started_on"]
    )
    return span // timedelta(milliseconds=1)


def _grade(row: dict[str, Any] | None) -> dict[str, Any]:
    """A claim's grade from its stored row; none when the judge didn't grade it."""
    if row is None or not row["graded"]:
        return {"grade": None, "judge_cost": Decimal(0)}
    return {
        "grade": {
            "score": Decimal(row["score"]),
            "letter": row["letter"],
            "same_grounds": Decimal(row["same_grounds"]),
            "same_section": Decimal(row["same_section"]),
            "same_grounds_matched": Decimal(row["same_grounds"]) > MATCHED,
            "same_section_matched": Decimal(row["same_section"]) > MATCHED,
        },
        "judge_cost": money.from_nanos(row["cost_nanos"]),
    }


def _claim_rows(run: dict[str, Any]) -> list[dict[str, Any]]:
    """Each claim of an evaluation: the agent's answer beside the handler's."""
    in_run, claims, key = tables.run_claims.c, tables.claims.c, tables.answer_key.c
    totals = usage.claim_totals(run["run_id"])
    graded = grading.grades(run["run_id"])
    with db.connection() as conn:
        rows = conn.execute(
            select(
                in_run.claim_id,
                in_run.source_claim_id,
                in_run.status,
                in_run.note,
                claims.decision,
                claims.payout_cents,
                claims.reason,
                key.decision.label("key_decision"),
                key.payout_cents.label("key_payout_cents"),
            )
            .join(tables.claims, claims.claim_id == in_run.claim_id)
            .join(
                tables.answer_key,
                (key.eval_set == run["eval_set"])
                & (key.claim_id == in_run.source_claim_id),
            )
            .where(in_run.run_id == run["run_id"])
            .order_by(in_run.source_claim_id)
        )
        found = [dict(row._mapping) for row in rows]
    result = []
    for row in found:
        payout = (
            None
            if row["payout_cents"] is None
            else money.from_cents(row["payout_cents"])
        )
        scored = {
            "decision": row["decision"],
            "payout": payout,
            "key_decision": row["key_decision"],
            "key_payout": money.from_cents(row["key_payout_cents"]),
        }
        claim_total = totals.get(row["claim_id"], {"cost": Decimal(0), "work_ms": 0})
        result.append(
            {
                "claim_id": row["claim_id"],
                "source_claim_id": row["source_claim_id"],
                "status": row["status"],
                "note": row["note"],
                "handler_decision": scored["key_decision"],
                "handler_payout": scored["key_payout"],
                "agent_decision": row["decision"],
                "agent_payout": payout,
                "reason": row["reason"],
                "right": scoring.is_right(scored),
                "mistake_cost": scoring.mistake_cost(scored),
                "cost": claim_total["cost"],
                "work_ms": claim_total["work_ms"],
                **_grade(graded.get(row["claim_id"])),
            }
        )
    return result


def _evaluation(run: dict[str, Any]) -> dict[str, Any]:
    """An evaluation's run record with its claims and its measures."""
    claims = _claim_rows(run)
    scored = [
        {
            "decision": claim["agent_decision"],
            "payout": claim["agent_payout"],
            "key_decision": claim["handler_decision"],
            "key_payout": claim["handler_payout"],
        }
        for claim in claims
    ]
    return {
        **run,
        "claims": claims,
        "measures": {
            **scoring.measures(scored, run["cost"], run["work_ms"], _run_ms(run)),
            **scoring.grade_measures(claims),
        },
    }


def get_evaluation(run_id: int) -> dict[str, Any]:
    """Return one evaluation with each claim's answers beside the handler's."""
    run = runs.get_run(run_id)
    if run["kind"] != RunKind.EVALUATION:
        raise NotFound(f"No evaluation {run_id}")
    return _evaluation(run)


def list_evaluations() -> list[dict[str, Any]]:
    """List the evaluations, newest first, with their measures."""
    run_column = tables.runs.c.run_id
    with db.connection() as conn:
        ids = [
            run_id
            for (run_id,) in conn.execute(
                select(run_column)
                .where(tables.runs.c.kind == RunKind.EVALUATION)
                .order_by(run_column.desc())
            )
        ]
    return [get_evaluation(run_id) for run_id in ids]
