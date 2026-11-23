"""A senior handler sends an approval back to the agent with a note; the agent takes it.

A sign-off and a send back both start from a claim waiting for sign-off, and one
conditional update decides between them: whichever comes first wins.
"""

from typing import Any

from sqlalchemy import delete, insert, select, update

from backend import claims, db, tables
from backend.errors import Conflict, Invalid
from backend.statuses import ClaimStatus, StepKind

MAX_NOTE_LENGTH = 1000
DECISION_COLUMNS = [
    "decision",
    "payout_cents",
    "reason",
    "policy_reference",
    "decided_by",
    "decided_on",
    "calculation",
    "manual_version",
]


def send_back_claim(
    claim_id: str, handler: dict[str, Any], note: str
) -> dict[str, Any]:
    """Send an approval waiting for sign-off back to the agent with the handler's note.

    The decision is kept with the note, who and when; the claim's own decision, its
    calculation for the attempt and its hold are cleared, so the agent decides again.
    """
    note = note.strip()
    if not note:
        raise Invalid("A note is needed to send a claim back")
    if len(note) > MAX_NOTE_LENGTH:
        raise Invalid(f"The note can be at most {MAX_NOTE_LENGTH} characters")
    row = claims.get_row(claim_id)
    if row["evaluation_run_id"] is not None:
        raise Conflict("An evaluation's claim can't be sent back")
    columns = tables.claims.c
    with db.connection() as conn:
        kept = conn.execute(
            select(*(columns[name] for name in DECISION_COLUMNS)).where(
                columns.claim_id == claim_id
            )
        ).one()
        sent = conn.execute(
            update(tables.claims)
            .where(
                columns.claim_id == claim_id,
                columns.status == ClaimStatus.WAITING_FOR_SIGN_OFF,
                columns.decision == "approve",
                columns.paid_cents.is_(None),
                columns.signed_off_by.is_(None),
            )
            .values(
                status=ClaimStatus.SENT_BACK,
                over_approval_limit=None,
                hold_reason=None,
                **dict.fromkeys(DECISION_COLUMNS),
            )
        )
        if sent.rowcount == 0:
            raise Conflict("Claim is not waiting for sign-off")
        now = db.now()
        conn.execute(
            insert(tables.sent_back_decisions).values(
                claim_id=claim_id,
                note=note,
                sent_back_by=handler["handler_id"],
                sent_back_on=now,
                **kept._mapping,
            )
        )
        conn.execute(
            delete(tables.payout_calculations).where(
                tables.payout_calculations.c.claim_id == claim_id,
                tables.payout_calculations.c.thread == row["thread"],
            )
        )
        conn.execute(
            insert(tables.claim_steps).values(
                claim_id=claim_id,
                recorded_on=now,
                kind=StepKind.NOTE,
                text=f"Sent back by {handler['name']}: {note}",
                details={},
            )
        )
    return claims.get_row(claim_id)


def take_claim(claim_id: str) -> dict[str, Any]:
    """Take a sent-back claim for the agent: in progress, once, for whoever is first."""
    claims.get_row(claim_id)
    columns = tables.claims.c
    with db.connection() as conn:
        taken = conn.execute(
            update(tables.claims)
            .where(
                columns.claim_id == claim_id, columns.status == ClaimStatus.SENT_BACK
            )
            .values(status=ClaimStatus.IN_PROGRESS, resume_heard_on=db.now())
        )
    if taken.rowcount == 0:
        raise Conflict("Claim is not sent back, or another agent has taken it")
    return claims.get_row(claim_id)
