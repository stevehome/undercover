"""A run: a dispatch working claims, with a row for each claim it works."""

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Connection, and_, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from backend import db, grading, money, quiet, tables, usage, versions
from backend.errors import Conflict, NotFound
from backend.statuses import ClaimStatus, ItemStatus, RunKind, RunStatus, Stage


class RunSettings(BaseModel):
    """What a run works to: the model, its reasoning effort and the version."""

    model: str
    reasoning_effort: str
    configuration_version: int

    def columns(self) -> dict[str, Any]:
        """Return the run's columns for these settings."""
        return {
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "configuration_version": self.configuration_version,
        }


QUIET_REASON = "The agent stopped answering"
NOT_TAKEN_REASON = "The agent did not take the work"
WORK_NAMES = {
    RunKind.DISPATCH: "A dispatch",
    RunKind.EVALUATION: "An evaluation",
    RunKind.IMPROVER: "An improvement round",
}


class RunAlreadyGoing(Conflict):
    """Only one dispatch, evaluation or round can be working at a time."""


def get_run(run_id: int) -> dict[str, Any]:
    """Return one run with its claims and its totals, or raise NotFound."""
    with db.connection() as conn:
        run = conn.execute(
            select(tables.runs).where(tables.runs.c.run_id == run_id)
        ).one_or_none()
        if run is None:
            raise NotFound(f"No run {run_id}")
        rows = conn.execute(
            select(
                tables.run_claims.c.claim_id,
                tables.run_claims.c.status,
                tables.run_claims.c.attempts,
                tables.run_claims.c.note,
            )
            .where(tables.run_claims.c.run_id == run_id)
            .order_by(tables.run_claims.c.position)
        )
        claims = [dict(row._mapping) for row in rows]
    return {
        **run._mapping,
        "claims": claims,
        **usage.run_totals(run_id),
        "summary": _summary(run_id),
    }


def _summary(run_id: int) -> dict[str, Any]:
    """Count how a run's claims turned out, from the records and with no model."""
    columns = tables.claims.c
    in_run = tables.run_claims.c
    with db.connection() as conn:
        rows = [
            dict(row._mapping)
            for row in conn.execute(
                select(
                    in_run.claim_id,
                    in_run.status.label("run_status"),
                    columns.decision,
                    columns.status,
                    columns.payout_cents,
                )
                .join(tables.claims, columns.claim_id == in_run.claim_id)
                .where(in_run.run_id == run_id)
                .order_by(in_run.position)
            )
        ]
    return summarize(rows)


def summarize(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Count how a run's claims turned out from rows of claim_id, run_status,
    decision, status and payout_cents."""
    return {
        "approved": sum(row["decision"] == "approve" for row in rows),
        "declined": sum(row["decision"] == "decline" for row in rows),
        "referred": sum(row["decision"] == "refer" for row in rows),
        "waiting_for_sign_off": [
            {
                "claim_id": row["claim_id"],
                "payout": money.from_cents(row["payout_cents"]),
            }
            for row in rows
            if row["status"] == ClaimStatus.WAITING_FOR_SIGN_OFF
        ],
        "left_for_a_handler": [
            row["claim_id"]
            for row in rows
            if row["run_status"] == ItemStatus.LEFT_FOR_A_HANDLER
        ],
        "still_in_progress": [
            row["claim_id"]
            for row in rows
            if row["run_status"] == ItemStatus.STILL_IN_PROGRESS
        ],
    }


def get_current_run() -> dict[str, Any] | None:
    """Return the most recently started run, or None before the first."""
    with db.connection() as conn:
        run_id = conn.execute(select(func.max(tables.runs.c.run_id))).scalar_one()
    return None if run_id is None else get_run(run_id)


def _claims_to_dispatch() -> list[str]:
    """List the queue's claims to work, oldest submitted first.

    Those in progress and those waiting, those sent back, and any approved and ready
    to pay that a restart left unpaid. A claim in progress whose resume the app has
    heard from lately is left to it. An evaluation's copies are never among them.
    """
    columns = tables.claims.c
    payable = and_(
        columns.decision == "approve",
        columns.paid_cents.is_(None),
        or_(columns.over_approval_limit == 0, columns.signed_off_by.is_not(None)),
    )
    with db.connection() as conn:
        rows = conn.execute(
            select(columns.claim_id)
            .where(
                columns.evaluation_run_id.is_(None),
                or_(
                    columns.status.in_(
                        [
                            ClaimStatus.WAITING,
                            ClaimStatus.IN_PROGRESS,
                            ClaimStatus.SENT_BACK,
                        ]
                    ),
                    payable,
                ),
                or_(
                    columns.status != ClaimStatus.IN_PROGRESS,
                    columns.resume_heard_on.is_(None),
                    columns.resume_heard_on < quiet.cutoff(),
                ),
            )
            .order_by(columns.submitted_on, columns.claim_id)
        )
        return [claim_id for (claim_id,) in rows]


def insert_run(conn: Connection, **values: Any) -> int:
    """Insert a running run and return its id.

    Raises RunAlreadyGoing while another run is running; the database decides.
    """
    try:
        return conn.execute(
            insert(tables.runs)
            .values(status=RunStatus.RUNNING, started_on=db.now(), **values)
            .returning(tables.runs.c.run_id)
        ).scalar_one()
    except IntegrityError as error:
        raise RunAlreadyGoing("Something is already running") from error


def insert_run_claims(
    conn: Connection, run_id: int, claims: list[tuple[str, str | None]]
) -> None:
    """Add a run's claims, each as (claim id, the claim it is a copy of), to do."""
    if claims:
        conn.execute(
            insert(tables.run_claims),
            [
                {
                    "run_id": run_id,
                    "claim_id": claim_id,
                    "source_claim_id": source_claim_id,
                    "position": position,
                    "status": ItemStatus.TO_DO,
                }
                for position, (claim_id, source_claim_id) in enumerate(claims)
            ],
        )


def create_dispatch(concurrency: int, settings: RunSettings) -> dict[str, Any]:
    """Start a dispatch of every claim in progress and every waiting claim."""
    versions.get_configuration(settings.configuration_version)
    claim_ids = _claims_to_dispatch()
    with db.connection() as conn:
        run_id = insert_run(
            conn,
            kind=RunKind.DISPATCH,
            concurrency=concurrency,
            **settings.columns(),
        )
        insert_run_claims(conn, run_id, [(claim_id, None) for claim_id in claim_ids])
    return get_run(run_id)


def update_run_claim(
    run_id: int, claim_id: str, status: str, note: str
) -> dict[str, Any]:
    """Update one claim of a run; `in progress` counts as an attempt."""
    attempt = 1 if status == ItemStatus.IN_PROGRESS else 0
    columns = tables.run_claims.c
    with db.connection() as conn:
        updated = conn.execute(
            update(tables.run_claims)
            .where(columns.run_id == run_id, columns.claim_id == claim_id)
            .values(status=status, note=note, attempts=columns.attempts + attempt)
            .returning(columns.claim_id, columns.status, columns.attempts, columns.note)
        ).one_or_none()
    if updated is None:
        raise NotFound(f"No claim {claim_id} in run {run_id}")
    return dict(updated._mapping)


def finish_run(run_id: int) -> dict[str, Any]:
    """Finish a run; an evaluation's claims are graded first.

    A run with claims never started, because its round spent its limit or stopped,
    ends as stopped, and is not graded.
    """
    run = get_run(run_id)
    if run["status"] != RunStatus.RUNNING:
        return run
    cut_short = run["round_id"] is not None and any(
        claim["status"] == ItemStatus.TO_DO for claim in run["claims"]
    )
    if run["kind"] == RunKind.EVALUATION and not cut_short:
        grading.grade_evaluation(run_id)
    with db.connection() as conn:
        conn.execute(
            update(tables.runs)
            .where(tables.runs.c.run_id == run_id)
            .values(
                status=RunStatus.STOPPED if cut_short else RunStatus.FINISHED,
                finished_on=db.now(),
            )
        )
    return get_run(run_id)


def stop_run(run_id: int, reason: str, with_round: bool = True) -> None:
    """Stop a run that is running, with the reason; anything else is left as it is.

    A round's stretch of work stops its round (unless `with_round` is false, as when
    a review is cleared), and every run under it stops too: the evaluation it is
    working. Stopping again, or a run already finished, is done.
    """
    columns = tables.runs.c
    with db.connection() as conn:
        stopped = conn.execute(
            update(tables.runs)
            .where(columns.run_id == run_id, columns.status == RunStatus.RUNNING)
            .values(
                status=RunStatus.STOPPED, finished_on=db.now(), stopped_reason=reason
            )
            .returning(columns.kind, columns.round_id)
        ).one_or_none()
        if stopped is None:
            return
        conn.execute(
            update(tables.runs)
            .where(columns.parent_run_id == run_id, columns.status == RunStatus.RUNNING)
            .values(
                status=RunStatus.STOPPED, finished_on=db.now(), stopped_reason=reason
            )
        )
        if stopped.kind == RunKind.IMPROVER and with_round:
            conn.execute(
                update(tables.rounds)
                .where(
                    tables.rounds.c.round_id == stopped.round_id,
                    tables.rounds.c.stage.not_in([Stage.FINISHED, Stage.STOPPED]),
                )
                .values(
                    stage=Stage.STOPPED, finished_on=db.now(), stopped_reason=reason
                )
            )


def hear_from_run(run_id: int) -> None:
    """Note that the agent is working a run, so the app counts it as alive."""
    get_run_row(run_id)
    with db.connection() as conn:
        conn.execute(
            update(tables.runs)
            .where(tables.runs.c.run_id == run_id)
            .values(heard_from_on=db.now())
        )


def get_run_row(run_id: int) -> dict[str, Any]:
    """Return a run's own columns, or raise NotFound."""
    with db.connection() as conn:
        row = conn.execute(
            select(tables.runs).where(tables.runs.c.run_id == run_id)
        ).one_or_none()
    if row is None:
        raise NotFound(f"No run {run_id}")
    return dict(row._mapping)


def running_work() -> str | None:
    """Name the work that is going, a dispatch, an evaluation or a round, or None."""
    columns = tables.runs.c
    with db.connection() as conn:
        kind = conn.execute(
            select(columns.kind).where(
                columns.status == RunStatus.RUNNING, columns.parent_run_id.is_(None)
            )
        ).scalar_one_or_none()
    return None if kind is None else WORK_NAMES[kind]


def stop_quiet_runs() -> list[int]:
    """Stop work the app hasn't heard of for five minutes, and say which runs.

    Counting from the later of its start and the agent's last word. A round's
    evaluation is never stopped on its own: it stops with its round.
    """
    columns = tables.runs.c
    with db.connection() as conn:
        quiet_runs = [
            run_id
            for (run_id,) in conn.execute(
                select(columns.run_id).where(
                    columns.status == RunStatus.RUNNING,
                    columns.parent_run_id.is_(None),
                    func.coalesce(columns.heard_from_on, columns.started_on)
                    < quiet.cutoff(),
                )
            )
        ]
    for run_id in quiet_runs:
        stop_run(run_id, QUIET_REASON)
    return quiet_runs
