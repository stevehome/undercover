import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from backend import db, decision_record, money, over_limit, tables
from backend.statuses import AppealStatus, ClaimStatus

DATA = Path(__file__).resolve().parents[2] / "data"
CLAIM_FILES = [
    "claims.json",
    "security/claims.json",
    "evals/held_out_claims.json",
    "evals/ombudsman/claims.json",
    "appeals/claims.json",
]


def rows(table, *where):
    with db.connection() as conn:
        return [dict(r._mapping) for r in conn.execute(select(table).where(*where))]


def earlier_claims():
    column = tables.claims.c
    return rows(tables.claims, column.status == ClaimStatus.DECIDED)


def test_the_queue_holds_the_waiting_claims_and_eight_decided(client):
    statuses = Counter(row["status"] for row in rows(tables.claims))
    assert statuses == {ClaimStatus.WAITING: 26, ClaimStatus.DECIDED: 8}


def test_the_appeals_are_in_their_states(client):
    appeals = rows(tables.appeals)
    states = Counter(a["status"] for a in appeals)
    assert states == {
        AppealStatus.WITH_THE_OMBUDSMAN: 2,
        AppealStatus.UPHELD: 3,
        AppealStatus.NOT_UPHELD: 3,
    }
    paid = rows(tables.redress_payments)
    assert len(paid) == 1
    upheld = {a["claim_id"] for a in appeals if a["status"] == AppealStatus.UPHELD}
    assert paid[0]["claim_id"] in upheld
    assert paid[0]["amount_cents"] == 21_710


def test_each_appeal_fits_its_claim_and_its_outcome(client):
    decided = {c["claim_id"]: c for c in earlier_claims()}
    for appeal in rows(tables.appeals):
        claim = decided[appeal["claim_id"]]
        assert claim["decision"] in ("approve", "decline")
        amounts = [
            appeal[f"{name}_cents"]
            for name in ("claim_amount", "compensation", "interest")
        ]
        if appeal["status"] == AppealStatus.UPHELD:
            assert None not in amounts
            assert min(amounts) >= 0
            assert sum(amounts) > 0
        else:
            assert amounts == [None, None, None]
        assert (appeal["reason"] is None) == (
            appeal["status"] == AppealStatus.WITH_THE_OMBUDSMAN
        )


def test_each_earlier_claim_has_a_complete_decision_record(client):
    for claim in earlier_claims():
        payout = money.from_cents(claim["payout_cents"])
        decision_record.Decision(
            decision=claim["decision"],
            payout=payout,
            reason=claim["reason"],
            policy_reference=claim["policy_reference"],
            decided_by=claim["decided_by"],
        )
        assert claim["decided_on"]
        assert claim["manual_version"]
        if claim["decision"] == "approve":
            lines = claim["calculation"]
            total = sum((Decimal(line["amount"]) for line in lines), Decimal(0))
            assert total == payout
            assert claim["paid_cents"] == claim["payout_cents"]
            assert claim["paid_on"]
        else:
            assert claim["paid_cents"] is None


def test_every_payment_over_the_limit_has_a_sign_off(client):
    over = [c for c in earlier_claims() if c["payout_cents"] > 100_000]
    assert over
    assert all(c["signed_off_by"] and c["signed_off_on"] for c in over)
    counts = over_limit.get()
    assert counts["paid_over_the_limit"] == len(over)
    assert counts["with_a_sign_off"] == len(over)


def test_the_database_refuses_a_second_appeal_and_a_second_payment(client):
    appeal = rows(tables.appeals)[0]
    payment = rows(tables.redress_payments)[0]
    with pytest.raises(IntegrityError), db.connection() as conn:
        conn.execute(insert(tables.appeals).values(**appeal))
    with pytest.raises(IntegrityError), db.connection() as conn:
        conn.execute(insert(tables.redress_payments).values(**payment))


def test_the_evaluation_sets_and_the_waiting_claims_are_as_they_were(client):
    with db.connection() as conn:
        held_out = conn.execute(
            select(func.count()).select_from(tables.held_out_claims)
        ).scalar_one()
        key = conn.execute(select(func.count()).select_from(tables.answer_key))
        key = key.scalar_one()
    assert (held_out, key) == (25, 50)
    appeal_ids = {c["claim_id"] for c in earlier_claims()}
    with db.connection() as conn:
        in_key = conn.execute(select(tables.answer_key.c.claim_id)).scalars().all()
    assert not appeal_ids & set(in_key)


def test_no_claim_id_is_used_twice_across_the_files():
    ids = []
    for name in CLAIM_FILES:
        ids += [c["claim_id"] for c in json.loads((DATA / name).read_text())]
    assert len(ids) == len(set(ids))
