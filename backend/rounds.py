"""Improvement rounds: a round's records, its stages, its verdict and its stopping.

A round is one run of the improver's recipe. Its records live here, and what the
improver may read of them is in `improver_view.py`.
"""

import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Connection, insert, select, update

from backend import (
    db,
    evaluations,
    money,
    platform_settings,
    runs,
    spending,
    tables,
    verdict,
    version_scores,
    versions,
)
from backend.errors import Conflict, NotFound
from backend.money import Cost
from backend.statuses import RunKind, RunStatus, Stage, Verdict

CLOSED = (Stage.FINISHED, Stage.STOPPED)


def get_row(round_id: int) -> dict[str, Any]:
    """Return a round's own columns, or raise NotFound."""
    with db.connection() as conn:
        row = conn.execute(
            select(tables.rounds).where(tables.rounds.c.round_id == round_id)
        ).one_or_none()
    if row is None:
        raise NotFound(f"No round {round_id}")
    return dict(row._mapping)


def require_open(round_id: int) -> dict[str, Any]:
    """Return an open round, or raise Conflict: a closed round records nothing."""
    row = get_row(round_id)
    if row["stage"] in CLOSED:
        raise Conflict(f"Round {round_id} is {row['stage']}")
    return row


def _group(settings: dict[str, Any], prefix: str) -> dict[str, Decimal]:
    return {
        key.removeprefix(f"{prefix}_"): Decimal(str(value))
        for key, value in settings.items()
        if key.startswith(f"{prefix}_")
    }


def begin_stretch(
    conn: Connection, round_id: int, model: str, reasoning_effort: str
) -> int:
    """Start a stretch of the improver's work, a run that holds the one-run rule.

    Raises RunAlreadyGoing if something else is running, before anything else is
    recorded in the caller's transaction.
    """
    return runs.insert_run(
        conn,
        kind=RunKind.IMPROVER,
        concurrency=1,
        model=model,
        reasoning_effort=reasoning_effort,
        configuration_version=versions.current_configuration()["version"],
        round_id=round_id,
    )


def create_round(handler_id: str, model: str, reasoning_effort: str) -> dict[str, int]:
    """Start a round and its first stretch of work, or raise RunAlreadyGoing."""
    with db.connection() as conn:
        round_id = conn.execute(
            insert(tables.rounds)
            .values(
                stage=Stage.FIRST_EVALUATIONS,
                progress=0,
                thread_id=f"round-{uuid.uuid4().hex}",
                recipe_version=versions.current_recipe()["version"],
                settings=platform_settings.snapshot(),
                started_by=handler_id,
                started_on=db.now(),
            )
            .returning(tables.rounds.c.round_id)
        ).scalar_one()
        run_id = begin_stretch(conn, round_id, model, reasoning_effort)
    return {"round_id": round_id, "run_id": run_id}


def record_stage(round_id: int, stage: Stage, progress: int) -> dict[str, Any]:
    """Record where an open round has got to; finishing it ends it."""
    require_open(round_id)
    with db.connection() as conn:
        conn.execute(
            update(tables.rounds)
            .where(tables.rounds.c.round_id == round_id)
            .values(
                stage=stage,
                progress=progress,
                finished_on=db.now() if stage in CLOSED else None,
            )
        )
    return get_row(round_id)


def stop_round(round_id: int) -> dict[str, Any]:
    """Stop an open round. What it kept before its verdict is nothing."""
    require_open(round_id)
    return record_stage(round_id, Stage.STOPPED, get_row(round_id)["progress"])


def start_evaluation(
    round_id: int,
    parent_run_id: int,
    eval_set: str,
    settings: runs.RunSettings,
    check_spending: bool,
) -> dict[str, Any]:
    """Start a whole-set evaluation for a round, inside its stretch of work.

    The improver's own evaluations are refused when one is likely to cost more than
    what is left of the round's limit; the first ones are not.
    """
    row = require_open(round_id)
    left = spending.left(round_id, row["settings"])
    if check_spending:
        estimate = spending.estimate(
            eval_set, settings.model, versions.current_configuration()["model"]
        )
        if left <= 0 or (estimate is not None and estimate > left):
            raise Conflict(
                f"An evaluation on the {eval_set} set is likely to cost "
                f"${estimate}, and ${left} is left of the round's "
                f"${spending.limit(row['settings'])}"
            )
    return evaluations.start_evaluation(
        eval_set,
        False,
        int(row["settings"]["improver_agents_at_once"]),
        settings,
        in_round=(round_id, parent_run_id),
    )


class ImproverCall(BaseModel):
    """One of the improver's model calls: its tokens and its cost."""

    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: Cost


def record_call(round_id: int, call: ImproverCall) -> dict[str, Any]:
    """Record one of the improver's model calls with its round, if the round is open."""
    require_open(round_id)
    with db.connection() as conn:
        conn.execute(
            insert(tables.improver_calls).values(
                round_id=round_id,
                cost_nanos=money.to_nanos(call.cost),
                **call.model_dump(exclude={"cost"}),
            )
        )
    return {"round_id": round_id}


def missing_first_evaluations(round_id: int) -> list[str]:
    """List the evaluations the current version still lacks, as sets to run."""
    require_open(round_id)
    return version_scores.missing_runs(versions.current_configuration()["version"])


def _stopped_evaluations(version: int) -> int:
    columns = tables.runs.c
    with db.connection() as conn:
        found = conn.execute(
            select(columns.run_id).where(
                columns.configuration_version == version,
                columns.round_id.is_not(None),
                columns.kind == RunKind.EVALUATION,
                columns.status == RunStatus.STOPPED,
            )
        )
        return len(found.all())


def record_verdict(round_id: int) -> dict[str, Any]:
    """Keep or roll back the version under test, by the round's own settings."""
    row = require_open(round_id)
    version = row["configuration_version"]
    if version is None:
        raise Conflict("No version is under test in this round")
    current = versions.current_configuration()["version"]
    old = version_scores.scores_on(current, "held_out")
    new = version_scores.scores_on(version, "held_out")
    settings = row["settings"]
    if _stopped_evaluations(version) or version_scores.missing_runs(version):
        kept, why = (
            False,
            "its evaluations did not all finish within the round's spending limit",
        )
    else:
        kept, why = verdict.decide(
            new,
            old,
            _group(settings, "objective"),
            _group(settings, "noise"),
            _group(settings, "tolerance"),
        )
    outcome = Verdict.KEPT if kept else Verdict.ROLLED_BACK
    with db.connection() as conn:
        conn.execute(
            update(tables.configurations)
            .where(tables.configurations.c.version == version)
            .values(verdict=outcome, verdict_reason=why)
        )
        conn.execute(
            update(tables.rounds)
            .where(tables.rounds.c.round_id == round_id)
            .values(
                stage=Stage.VERDICT,
                held_out_before=old,
                held_out_after=new,
                verdict=outcome,
                verdict_reason=why,
            )
        )
    return {
        "version": version,
        "verdict": outcome,
        "reason": why,
        "before": old,
        "after": new,
    }
