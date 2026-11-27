import json

import pytest
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from agent import copilot_turns
from agent.tests import copilot_helpers as helpers
from agent.tests import records
from agent.tests.copilot_helpers import (
    answer,
    begin,
    read,
    reply,
    seen_model,
    tool_call,
    tool_result,
    turn_for,
)
from backend import copilot_turns as app_turns
from conftest import DANA, MARCUS

CLAIM = "CLM-1001"
OTHER = "CLM-1002"
ASK = "Sign off on CLM-1001"
SIGN_OFF = ("sign_off_claim", {"claim_id": CLAIM})


def hold(backend, claim_id=CLAIM, payout="1200.00"):
    """Leave a claim approved over the limit, waiting for a sign-off."""
    records.calculated(claim_id, payout)
    backend.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": "approve",
            "payout": payout,
            "reason": "Covered by section 3.",
            "policy_reference": "Section 3",
            "decided_by": "A test agent",
        },
    )


def pause(backend, token_for, email=DANA, calls=(SIGN_OFF,), saver=None):
    return helpers.pause(token_for, ASK, email, calls, saver)


def test_a_sign_off_pauses_with_a_card_from_our_records_and_pays_nothing(
    app_client, backend, as_handler, token_for
):
    hold(backend)

    conversation, _, model = pause(backend, token_for)

    seen = read(backend, conversation, as_handler)
    customer = backend.get(f"/api/claims/{CLAIM}").json()["customer_id"]
    name = backend.get(f"/api/customers/{customer}").json()["name"]
    assert seen["status"] == "waiting for a confirmation"
    assert seen["card"] == {
        "kind": "sign_off",
        "claim_id": CLAIM,
        "customer": {"customer_id": customer, "name": name},
        "payout": "1200.00",
        "reason": "Covered by section 3.",
    }
    assert len(model.seen) == 1
    assert backend.get(f"/api/claims/{CLAIM}").json()["paid_amount"] is None
    assert not [r for r in app_client.requests if r[0] == "POST" and "sign-off" in r[1]]


def test_a_handler_who_cant_sign_off_is_declined_in_code_with_no_card_and_no_pause(
    app_client, backend, as_handler, token_for
):
    hold(backend)

    conversation, _, model = pause(backend, token_for, email=MARCUS)

    seen = read(backend, conversation, as_handler, MARCUS)
    assert (seen["status"], seen["card"]) == ("done", None)
    step = seen["steps"][0]
    assert (step["tool"], step["state"]) == ("sign_off_claim", "refused")
    assert "Marcus Oyelaran can't sign off" in step["reason"]
    assert "can't sign off" in tool_result(model, "sign_off_claim").content
    assert backend.get(f"/api/claims/{CLAIM}").json()["paid_amount"] is None


def test_a_claim_that_isnt_waiting_is_declined_the_same_way(
    app_client, backend, as_handler, token_for
):
    conversation, _, _ = pause(backend, token_for)

    seen = read(backend, conversation, as_handler)
    assert (seen["status"], seen["card"]) == ("done", None)
    assert "isn't waiting for a sign-off" in seen["steps"][0]["reason"]


def test_a_fresh_copilot_given_the_answer_signs_off_once_and_repeats_nothing(
    app_client, backend, as_handler, token_for
):
    hold(backend)
    conversation, saver, first = pause(backend, token_for)
    posts = [r for r in app_client.requests if r[0] == "POST"]

    second = answer(conversation, saver, token_for, True)

    paid = backend.get(f"/api/claims/{CLAIM}").json()
    assert (paid["status"], paid["paid_amount"], paid["signed_off_by"]) == (
        "decided",
        "1200.00",
        "HND-01",
    )
    sign_offs = [
        r for r in app_client.requests if r[0] == "POST" and "sign-off" in r[1]
    ]
    assert len(sign_offs) == 1
    assert [r for r in app_client.requests if r[0] == "POST"][: len(posts)] == posts
    assert (len(first.seen), len(second.seen)) == (1, 1)
    seen = read(backend, conversation, as_handler)
    assert (seen["status"], seen["messages"][-1]["text"]) == ("done", "Back again.")
    assert seen["steps"][-1]["state"] == "done"


def test_cancel_pays_nothing_and_the_copilot_says_so(
    app_client, backend, as_handler, token_for
):
    hold(backend)
    conversation, saver, _ = pause(backend, token_for)

    model = answer(conversation, saver, token_for, False)

    claim = backend.get(f"/api/claims/{CLAIM}").json()
    assert (claim["status"], claim["paid_amount"]) == ("waiting for sign-off", None)
    assert "cancelled" in tool_result(model, "sign_off_claim").content
    seen = read(backend, conversation, as_handler)
    assert seen["steps"][-1]["state"] == "refused"
    assert seen["status"] == "done"


def test_a_card_that_no_longer_matches_the_claim_pays_nothing(
    app_client, backend, token_for
):
    hold(backend)
    conversation, saver, _ = pause(backend, token_for)
    shown = app_turns.answer_confirmation(
        conversation.conversation_id, conversation.handler_id
    )
    other = {**shown, "payout": "50.00"}
    model = seen_model(reply("It changed."))
    turn = turn_for(conversation, DANA, model, saver, token_for)

    copilot_turns.answer_confirmation(turn, True, other)

    assert backend.get(f"/api/claims/{CLAIM}").json()["paid_amount"] is None
    assert "changed" in tool_result(model, "sign_off_claim").content


def test_a_mixed_reply_runs_the_lookup_and_pauses_once(
    app_client, backend, as_handler, token_for
):
    hold(backend)
    calls = (("list_claims", {}), SIGN_OFF)
    conversation, saver, _ = pause(backend, token_for, calls=calls)
    assert (
        read(backend, conversation, as_handler)["status"]
        == "waiting for a confirmation"
    )
    assert not [r for r in app_client.requests if r == ("GET", "/api/claims")]

    answer(conversation, saver, token_for, True)

    assert len([r for r in app_client.requests if r == ("GET", "/api/claims")]) == 1
    seen = read(backend, conversation, as_handler)
    assert sorted(s["tool"] for s in seen["steps"]) == [
        "list_claims",
        "sign_off_claim",
    ]
    assert backend.get(f"/api/claims/{CLAIM}").json()["paid_amount"] == "1200.00"


def test_a_second_sign_off_in_the_same_reply_is_answered_one_at_a_time(
    app_client, backend, as_handler, token_for
):
    hold(backend)
    hold(backend, OTHER, "1300.00")
    calls = (SIGN_OFF, ("sign_off_claim", {"claim_id": OTHER}))
    conversation, saver, _ = pause(backend, token_for, calls=calls)

    model = answer(conversation, saver, token_for, True)

    assert backend.get(f"/api/claims/{CLAIM}").json()["paid_amount"] == "1200.00"
    assert backend.get(f"/api/claims/{OTHER}").json()["paid_amount"] is None
    messages = [m for m in model.seen[-1] if isinstance(m, ToolMessage)]
    assert "One payment at a time" in messages[1].content
    assert json.loads(str(messages[0].content))["paid_amount"] == "1200.00"


@pytest.mark.parametrize("email", [DANA, MARCUS])
def test_the_sign_off_tool_refuses_without_a_confirmation(
    app_client, backend, token_for, email
):
    hold(backend)
    conversation = begin(email, ASK)
    model = seen_model(tool_call("sign_off_claim", {"claim_id": CLAIM}), reply("No."))
    turn = turn_for(conversation, email, model, InMemorySaver(), token_for)

    copilot_turns.work_turn(turn, ASK)

    assert backend.get(f"/api/claims/{CLAIM}").json()["paid_amount"] is None
