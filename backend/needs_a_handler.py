"""What in the queue needs a handler, counted from the records.

Payouts held for a sign-off, claims the agent referred or left for a handler, and
claims sent back to the agent that it hasn't worked yet.
"""

from typing import Any

from sqlalchemy import func, or_, select

from backend import appeals, db, money, tables
from backend.statuses import ClaimStatus, ItemStatus, RunKind


def _latest_dispatch() -> Any:
    runs = tables.runs.c
    return (
        select(func.max(runs.run_id))
        .where(runs.kind == RunKind.DISPATCH)
        .scalar_subquery()
    )


def get() -> dict[str, list[dict[str, Any]]]:
    """Return the groups that need a handler, each oldest first.

    Three groups of claims, and the appeals waiting for an outcome and the redress
    waiting for a sign-off.
    """
    claims = tables.claims.c
    in_run = tables.run_claims.c
    left = (
        select(in_run.claim_id)
        .where(
            in_run.run_id == _latest_dispatch(),
            in_run.status == ItemStatus.LEFT_FOR_A_HANDLER,
        )
        .scalar_subquery()
    )
    with db.connection() as conn:
        rows = [
            dict(row._mapping)
            for row in conn.execute(
                select(
                    claims.claim_id,
                    claims.summary,
                    claims.status,
                    claims.decision,
                    claims.payout_cents,
                    claims.hold_reason,
                    claims.claim_id.in_(left).label("left_for_a_handler"),
                )
                .where(
                    claims.evaluation_run_id.is_(None),
                    or_(
                        claims.status.in_(
                            [ClaimStatus.WAITING_FOR_SIGN_OFF, ClaimStatus.SENT_BACK]
                        ),
                        claims.decision == "refer",
                        claims.claim_id.in_(left),
                    ),
                )
                .order_by(claims.submitted_on, claims.claim_id)
            )
        ]
    held = [r for r in rows if r["status"] == ClaimStatus.WAITING_FOR_SIGN_OFF]
    sent_back = [r for r in rows if r["status"] == ClaimStatus.SENT_BACK]
    others = [r for r in rows if r not in held and r not in sent_back]
    return {
        "held_for_sign_off": [_held(r) for r in held],
        "referred_or_left_for_a_handler": [_plain(r) for r in others],
        "sent_back_not_yet_worked": [_plain(r) for r in sent_back],
        "appeals_waiting_for_an_outcome": [
            _appeal(r) for r in appeals.waiting_for_outcome()
        ],
        "redress_waiting_for_sign_off": [
            {**_appeal(r), "redress": money.from_cents(appeals.redress_cents(r))}
            for r in appeals.redress_waiting()
        ],
    }


def _appeal(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": row["claim_id"],
        "summary": row["claim_summary"],
        "ombudsman_reference": row["ombudsman_reference"],
    }


def _plain(row: dict[str, Any]) -> dict[str, Any]:
    return {"claim_id": row["claim_id"], "summary": row["summary"]}


def _held(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **_plain(row),
        "payout": money.from_cents(row["payout_cents"]),
        "hold_reason": row["hold_reason"],
    }
