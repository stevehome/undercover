"""A claim's latest payout calculation for its current attempt.

A claim carried on keeps its attempt, and a claim worked afresh is a new one, so a
calculation never carries from one attempt to the next.
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import insert, select, update

from backend import db, money, tables


def keep(claim_id: str, thread: int, calculation: dict[str, Any]) -> None:
    """Keep a calculation as the attempt's latest, in place of an earlier one."""
    columns = tables.payout_calculations.c
    values = {
        "steps": calculation["calculation"],
        "payout_cents": money.to_cents(calculation["payout"]),
        "calculated_on": db.now(),
    }
    with db.connection() as conn:
        updated = conn.execute(
            update(tables.payout_calculations)
            .where(columns.claim_id == claim_id, columns.thread == thread)
            .values(**values)
        )
        if updated.rowcount == 0:
            conn.execute(
                insert(tables.payout_calculations).values(
                    claim_id=claim_id, thread=thread, **values
                )
            )


def latest(claim_id: str, thread: int) -> tuple[list[dict[str, Any]], Decimal] | None:
    """Return the attempt's latest calculation's lines and payout, or None."""
    columns = tables.payout_calculations.c
    with db.connection() as conn:
        row = conn.execute(
            select(columns.steps, columns.payout_cents).where(
                columns.claim_id == claim_id, columns.thread == thread
            )
        ).one_or_none()
    return None if row is None else (row.steps, money.from_cents(row.payout_cents))
