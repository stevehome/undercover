"""Paying an upheld appeal's redress: once, from the amounts as recorded."""

from typing import Any

from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from backend import appeals, db, tables
from backend.errors import Conflict
from backend.statuses import AppealStatus


def pay(claim_id: str, handler: dict[str, Any]) -> dict[str, Any]:
    """Pay an upheld appeal's redress, signed off by the handler, and return the appeal.

    The amount is the appeal's three amounts together; the request holds none, so a
    handler can't change it. The database refuses a second payment. The route has
    checked that the handler can sign off a payout over the approval limit.
    """
    row = appeals.get_row(claim_id)
    if row["status"] != AppealStatus.UPHELD:
        raise Conflict("Only an upheld appeal has redress to pay")
    try:
        with db.connection() as conn:
            conn.execute(
                insert(tables.redress_payments).values(
                    claim_id=claim_id,
                    amount_cents=appeals.redress_cents(row),
                    signed_off_by=handler["handler_id"],
                    paid_on=db.now(),
                )
            )
    except IntegrityError as error:
        raise Conflict("The redress has already been paid") from error
    return appeals.get_row(claim_id)
