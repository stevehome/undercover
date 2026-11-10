"""A run: a dispatch working claims, with a row for each claim it works."""

from typing import Any

from sqlalchemy import and_, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from backend import db, money, tables, usage
from backend.errors import Conflict, NotFound
from backend.statuses import ClaimStatus, ItemStatus, RunKind, RunStatus


class RunAlreadyGoing(Conflict):
    """Only one dispatch or evaluation can run at a time."""


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
            row._mapping
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
    """List the claims to work, oldest submitted first.

    Those in progress and those waiting, and any approved and ready to pay
    that a restart left unpaid.
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
                or_(
                    columns.status.in_([ClaimStatus.WAITING, ClaimStatus.IN_PROGRESS]),
                    payable,
                )
            )
            .order_by(columns.submitted_on, columns.claim_id)
        )
        return [claim_id for (claim_id,) in rows]


def create_dispatch(
    concurrency: int, model: str, reasoning_effort: str
) -> dict[str, Any]:
    """Start a dispatch of every claim in progress and every waiting claim.

    Raises RunAlreadyGoing while another run is running; the database decides.
    """
    claim_ids = _claims_to_dispatch()
    try:
        with db.connection() as conn:
            run_id = conn.execute(
                insert(tables.runs)
                .values(
                    kind=RunKind.DISPATCH,
                    status=RunStatus.RUNNING,
                    concurrency=concurrency,
                    model=model,
                    reasoning_effort=reasoning_effort,
                    started_on=db.now(),
                )
                .returning(tables.runs.c.run_id)
            ).scalar_one()
            if claim_ids:
                conn.execute(
                    insert(tables.run_claims),
                    [
                        {
                            "run_id": run_id,
                            "claim_id": claim_id,
                            "position": position,
                            "status": ItemStatus.TO_DO,
                        }
                        for position, claim_id in enumerate(claim_ids)
                    ],
                )
    except IntegrityError as error:
        raise RunAlreadyGoing("A dispatch or evaluation is already running") from error
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
    """Finish a run."""
    get_run(run_id)
    with db.connection() as conn:
        conn.execute(
            update(tables.runs)
            .where(tables.runs.c.run_id == run_id)
            .values(status=RunStatus.FINISHED, finished_on=db.now())
        )
    return get_run(run_id)


def stop_unfinished_runs() -> int:
    """Mark every run still running as stopped, and say how many there were."""
    with db.connection() as conn:
        stopped = conn.execute(
            update(tables.runs)
            .where(tables.runs.c.status == RunStatus.RUNNING)
            .values(status=RunStatus.STOPPED, finished_on=db.now())
        )
    return stopped.rowcount
