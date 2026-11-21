"""A request holds at most one database connection at a time.

The backend has a pool of a few connections shared by every request. A request that
holds one while it asks for a second can wait for a connection that another such
request is holding for the same reason: a deadlock that stops the whole backend.
"""

import threading
from contextlib import contextmanager

import pytest

from backend import db
from backend.tests import records

APPROVAL = {
    "decision": "approve",
    "payout": "420.00",
    "reason": "Stubbed.",
    "policy_reference": "Section 3",
}
OVER_THE_LIMIT = {**APPROVAL, "payout": "1200.00"}
STEP = {"kind": "note", "text": "A step", "details": {}}


@pytest.fixture
def deepest(monkeypatch):
    """Track how many connections one thread holds at once; return the worst so far."""
    held = threading.local()
    worst = [0]
    real = db.connection

    @contextmanager
    def tracked():
        held.count = getattr(held, "count", 0) + 1
        worst[0] = max(worst[0], held.count)
        try:
            with real() as conn:
                yield conn
        finally:
            held.count -= 1

    monkeypatch.setattr(db, "connection", tracked)
    return worst


def test_deciding_paying_and_recording_hold_one_connection_at_a_time(client, deepest):
    records.decide(client, "CLM-1001", APPROVAL)
    client.post("/api/claims/CLM-1001/payment", json={"amount": "420.00"})
    client.post("/api/claims/CLM-1001/steps", json=STEP)
    client.get("/api/claims/CLM-1001")
    client.get("/api/claims/CLM-1001/steps")

    assert deepest[0] == 1


def test_a_decline_a_hold_and_a_sign_off_hold_one_connection_at_a_time(client, deepest):
    refer = {**APPROVAL, "decision": "refer", "payout": "0.00"}
    records.decide(client, "CLM-1002", refer)
    records.decide(client, "CLM-1003", APPROVAL)
    client.post("/api/claims/CLM-1003/hold", json={"reason": "gateway"})
    client.post("/api/claims/CLM-1003/sign-off")
    records.decide(client, "CLM-1004", OVER_THE_LIMIT)
    client.post("/api/claims/CLM-1004/sign-off")

    assert deepest[0] == 1


def test_working_out_a_payout_and_requeueing_hold_one_connection_at_a_time(
    client, deepest
):
    records.calculate(client, "CLM-1005", "300.00")
    client.post("/api/claims/CLM-1005/requeue")

    assert deepest[0] == 1
