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


def _copies(run_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    """Each run's claims in order, with the agent's answer beside the handler's."""
    in_run, claims, key = tables.run_claims.c, tables.claims.c, tables.answer_key.c
    run = tables.runs.c
    found: dict[int, list[dict[str, Any]]] = {run_id: [] for run_id in run_ids}
    with db.connection() as conn:
        rows = conn.execute(
            select(
                in_run.run_id,
                in_run.claim_id,
                in_run.source_claim_id,
                in_run.status.label("run_status"),
                in_run.note,
                claims.decision,
                claims.status,
                claims.payout_cents,
                claims.reason,
                key.decision.label("key_decision"),
                key.payout_cents.label("key_payout_cents"),
            )
            .join(tables.claims, claims.claim_id == in_run.claim_id)
            .join(tables.runs, run.run_id == in_run.run_id)
            .join(
                tables.answer_key,
                (key.eval_set == run.eval_set)
                & (key.claim_id == in_run.source_claim_id),
            )
            .where(in_run.run_id.in_(run_ids))
            .order_by(in_run.run_id, in_run.position)
        )
        for row in rows:
            found[row.run_id].append(dict(row._mapping))
    return found


def _claim_rows(
    copies: list[dict[str, Any]],
    totals: dict[str, dict[str, Any]],
    graded: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Each claim of an evaluation: the agent's answer beside the handler's."""
    result = []
    for row in sorted(copies, key=lambda copy: copy["source_claim_id"]):
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
                "status": row["run_status"],
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


def _evaluations(found: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Evaluation runs with their claims and measures, in a fixed number of queries."""
    ids = [run["run_id"] for run in found]
    copies, totals, graded = _copies(ids), usage.totals(ids), grading.grades(ids)
    evaluations = []
    for run in found:
        run_id, total = run["run_id"], totals[run["run_id"]]
        claims = _claim_rows(copies[run_id], total["claims"], graded[run_id])
        scored = [
            {
                "decision": claim["agent_decision"],
                "payout": claim["agent_payout"],
                "key_decision": claim["handler_decision"],
                "key_payout": claim["handler_payout"],
            }
            for claim in claims
        ]
        evaluations.append(
            {
                **run,
                "claims": claims,
                "model_calls": total["model_calls"],
                "total_tokens": total["total_tokens"],
                "cost": total["cost"],
                "work_ms": total["work_ms"],
                "summary": runs.summarize(copies[run_id]),
                "measures": {
                    **scoring.measures(
                        scored, total["cost"], total["work_ms"], _run_ms(run)
                    ),
                    **scoring.grade_measures(claims),
                },
            }
        )
    return evaluations


def _evaluation_runs(*conditions: Any) -> list[dict[str, Any]]:
    """The evaluation runs that meet the conditions, newest first."""
    columns = tables.runs.c
    with db.connection() as conn:
        rows = conn.execute(
            select(tables.runs)
            .where(columns.kind == RunKind.EVALUATION, *conditions)
            .order_by(columns.run_id.desc())
        )
        return [dict(row._mapping) for row in rows]


def get_evaluation(run_id: int) -> dict[str, Any]:
    """Return one evaluation with each claim's answers beside the handler's."""
    found = _evaluation_runs(tables.runs.c.run_id == run_id)
    if not found:
        raise NotFound(f"No evaluation {run_id}")
    return _evaluations(found)[0]


def get_evaluations(run_ids: list[int]) -> list[dict[str, Any]]:
    """Return the evaluations with these run ids, in a fixed number of queries."""
    return _evaluations(_evaluation_runs(tables.runs.c.run_id.in_(run_ids)))


def list_evaluations() -> list[dict[str, Any]]:
    """List the evaluations, newest first, with their measures."""
    return _evaluations(_evaluation_runs())
