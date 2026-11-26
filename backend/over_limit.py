"""Payments over the approval limit and the sign-offs behind them."""

from decimal import Decimal
from typing import Any

from sqlalchemy import select

from backend import db, money, platform_settings, tables


def get() -> dict[str, Any]:
    """Return the claims in our queue paid over the approval limit.

    Each has the handler who signed it off, if one did. The counts are what the
    success criterion asks: how many were paid over the limit, and how many of
    those carry a sign-off.
    """
    limit = platform_settings.get("payout_approval_limit")
    columns = tables.claims.c
    with db.connection() as conn:
        rows = conn.execute(
            select(columns.claim_id, columns.paid_cents, columns.signed_off_by)
            .where(
                columns.evaluation_run_id.is_(None),
                columns.paid_cents > money.to_cents(Decimal(limit)),
            )
            .order_by(columns.claim_id)
        )
        claims = [
            {
                "claim_id": row.claim_id,
                "paid": money.from_cents(row.paid_cents),
                "signed_off_by": row.signed_off_by,
            }
            for row in rows
        ]
    return {
        "approval_limit": limit,
        "paid_over_the_limit": len(claims),
        "with_a_sign_off": sum(c["signed_off_by"] is not None for c in claims),
        "claims": claims,
    }
