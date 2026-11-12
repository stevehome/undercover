import json
from pathlib import Path

from sqlalchemy import func, select

from backend import db, tables

EVALS = Path(__file__).resolve().parents[2] / "data" / "evals"


def handlers_reasons():
    files = ("decisions.json", "held_out_decisions.json")
    return [
        text
        for name in files
        for answer in json.loads((EVALS / name).read_text())
        for text in (answer["reason"], answer["reference"])
        if len(text) > 40
    ]


def test_no_claim_operation_returns_a_handlers_reason(client):
    responses = [client.get("/api/claims").text]
    for claim in client.get("/api/claims").json():
        claim_id = claim["claim_id"]
        responses.append(client.get(f"/api/claims/{claim_id}").text)
        responses.append(client.get(f"/api/claims/{claim_id}/steps").text)
    responses.append(client.get("/api/configuration/current").text)
    everything = "\n".join(responses)

    reasons = handlers_reasons()

    assert len(reasons) > 25
    assert not [reason for reason in reasons if reason in everything]


def test_the_answer_key_holds_every_reason_and_reference(client):
    with db.connection() as conn:
        count = conn.execute(
            select(func.count()).select_from(tables.answer_key)
        ).scalar_one()
        empty = conn.execute(
            select(func.count())
            .select_from(tables.answer_key)
            .where(tables.answer_key.c.reason == "")
        ).scalar_one()

    assert count == 50
    assert empty == 0
