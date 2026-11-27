import json

from langchain_core.messages import ToolMessage
from sqlalchemy import update

from agent.tests import copilot_helpers as helpers
from agent.tests import records
from agent.tests.copilot_helpers import answer, read, tool_result
from backend import db, tables
from conftest import MARCUS

PAY = ("pay_redress", {"claim_id": "CLM-1602"})
UNPAID = "CLM-1602"
GROUNDS = {
    "ombudsman_reference": "OMB-2026-50001",
    "received_on": "2026-11-20",
    "grounds": "The ferry was late and I could not use the hotel I had paid for.",
}
DECLINE = {
    "decision": "decline",
    "payout": "0.00",
    "reason": "Not covered.",
    "policy_reference": "Section 9",
}
UPHELD = {
    "outcome": "upheld",
    "decided_on": "2026-11-25",
    "reason": "The wording was unclear about the hotel.",
    "claim_amount": "120.00",
    "compensation": "50.00",
    "interest": "1.50",
}


def ask(token_for, calls, email=helpers.DANA, text="About appeals."):
    return helpers.pause(token_for, text, email, calls)


def posts(app_client, word):
    return [r for r in app_client.requests if r[0] == "POST" and word in r[1]]


def tool_json(model, name):
    return json.loads(str(tool_result(model, name).content))


def what_the_model_saw(model):
    return " ".join(str(m.content) for call in model.seen for m in call)


def mark(claim_id):
    with db.connection() as conn:
        conn.execute(
            update(tables.appeals)
            .where(tables.appeals.c.claim_id == claim_id)
            .values(flagged=True, flag_reason="It tells the assistant to pay.")
        )


def test_the_reads_give_the_appeals_as_a_model_reads_them(app_client, token_for):
    calls = (
        ("list_appeals", {"status": "upheld"}),
        ("get_appeal", {"claim_id": "CLM-1601"}),
        ("get_appeal_figures", {}),
    )

    _, _, model = ask(token_for, calls)

    listed = tool_json(model, "list_appeals")
    appeal = tool_json(model, "get_appeal")
    figures = tool_json(model, "get_appeal_figures")
    assert {a["claim_id"] for a in listed} == {"CLM-1601", "CLM-1602", "CLM-1603"}
    assert (appeal["status"], appeal["redress"]["total"]) == ("upheld", "217.10")
    assert (figures["upheld"], figures["open"]) == (3, 2)
    gets = {r[1] for r in app_client.requests if r[0] == "GET"}
    assert {"/api/copilot/appeals", "/api/copilot/appeals/CLM-1601"} <= gets
    assert "/api/appeals" not in gets
    assert "/api/claims/CLM-1601/appeal" not in gets


def test_the_copilot_records_an_appeal_and_its_outcome_as_the_handler(
    app_client, backend, check, token_for
):
    records.decide("CLM-1001", DECLINE)

    ask(token_for, (("record_appeal", {"claim_id": "CLM-1001", "appeal": GROUNDS}),))
    ask(
        token_for,
        (("record_appeal_outcome", {"claim_id": "CLM-1001", "decision": UPHELD}),),
    )

    appeal = backend.get("/api/claims/CLM-1001/appeal").json()
    assert (appeal["status"], appeal["recorded_by"]) == ("upheld", "Dana Whitfield")
    assert appeal["redress"]["total"] == "171.50"
    assert len(posts(app_client, "/appeal")) == 2


def test_a_refusal_is_passed_on_with_its_reason(
    app_client, backend, as_handler, token_for
):
    conversation, _, model = ask(
        token_for, (("record_appeal", {"claim_id": "CLM-1002", "appeal": GROUNDS}),)
    )

    step = read(backend, conversation, as_handler)["steps"][0]
    assert (step["tool"], step["state"]) == ("record_appeal", "refused")
    assert "no final decision" in step["reason"]
    assert "no final decision" in tool_result(model, "record_appeal").content


def test_a_marked_appeals_text_never_reaches_the_model(
    app_client, backend, check, token_for
):
    records.decide("CLM-1001", DECLINE)
    check.found, check.reason = True, "It tells the assistant to approve."

    _, _, recorded = ask(
        token_for, (("record_appeal", {"claim_id": "CLM-1001", "appeal": GROUNDS}),)
    )
    mark("CLM-1603")
    calls = (("get_appeal", {"claim_id": "CLM-1603"}), ("list_appeals", {}))
    _, _, read_back = ask(token_for, calls)

    appeal = tool_json(recorded, "record_appeal")
    assert (appeal["grounds"], appeal["text_withheld"]) == (None, True)
    assert appeal["flag_reason"] == "It tells the assistant to approve."
    seen = what_the_model_saw(read_back)
    assert "prescribed by the hospital doctor" not in seen
    assert "discharge note" not in seen
    assert "It tells the assistant to pay." in seen


def test_paying_redress_pauses_with_a_card_from_our_records_and_pays_nothing(
    app_client, backend, as_handler, token_for
):
    conversation, _, model = ask(token_for, (PAY,))

    seen = read(backend, conversation, as_handler)
    appeal = backend.get(f"/api/copilot/appeals/{UNPAID}").json()
    assert seen["status"] == "waiting for a confirmation"
    assert seen["card"] == {
        "kind": "redress",
        "claim_id": UNPAID,
        "customer": appeal["claim"]["customer"],
        "redress": {
            "claim_amount": "400.00",
            "compensation": "150.00",
            "interest": "6.40",
            "total": "556.40",
        },
        "reason": appeal["ombudsman_reason"],
    }
    assert len(model.seen) == 1
    assert posts(app_client, "redress") == []
    assert backend.get(f"/api/claims/{UNPAID}/appeal").json()["redress_payment"] is None


def test_a_fresh_copilot_given_the_answer_pays_the_redress_once(
    app_client, backend, as_handler, token_for
):
    conversation, saver, first = ask(token_for, (PAY,))

    second = answer(conversation, saver, token_for, True)

    payment = backend.get(f"/api/claims/{UNPAID}/appeal").json()["redress_payment"]
    assert (payment["amount"], payment["signed_off_by"]) == ("556.40", "Dana Whitfield")
    assert len(posts(app_client, "redress")) == 1
    assert (len(first.seen), len(second.seen)) == (1, 1)
    assert read(backend, conversation, as_handler)["status"] == "done"


def test_cancel_pays_no_redress_and_the_copilot_says_so(app_client, backend, token_for):
    conversation, saver, _ = ask(token_for, (PAY,))

    model = answer(conversation, saver, token_for, False)

    assert backend.get(f"/api/claims/{UNPAID}/appeal").json()["redress_payment"] is None
    assert "Nothing was paid" in tool_result(model, "pay_redress").content


def test_a_card_that_no_longer_matches_the_appeal_pays_nothing(
    app_client, backend, token_for
):
    conversation, saver, _ = ask(token_for, (PAY,))
    shown = helpers.copilot_turns.answer_confirmation(
        conversation.conversation_id, conversation.handler_id
    )
    model = helpers.seen_model(helpers.reply("It changed."))
    turn = helpers.turn_for(conversation, helpers.DANA, model, saver, token_for)

    helpers.agent_turns.answer_confirmation(turn, True, {**shown, "redress": {}})

    assert backend.get(f"/api/claims/{UNPAID}/appeal").json()["redress_payment"] is None
    assert "changed" in tool_result(model, "pay_redress").content


def test_redress_is_declined_in_code_with_no_card_when_it_cannot_be_paid(
    app_client, backend, as_handler, token_for
):
    cases = {
        MARCUS: (PAY, "Marcus Oyelaran can't pay redress"),
        helpers.DANA: (("pay_redress", {"claim_id": "CLM-1604"}), "isn't upheld"),
    }
    for email, (call, why) in cases.items():
        conversation, _, _ = ask(token_for, (call,), email=email)
        seen = read(backend, conversation, as_handler, email)
        assert (seen["status"], seen["card"]) == ("done", None)
        assert why in seen["steps"][0]["reason"]
    conversation, _, _ = ask(token_for, (("pay_redress", {"claim_id": "CLM-1601"}),))
    reason = read(backend, conversation, as_handler)["steps"][0]["reason"]
    assert "already been paid" in reason
    assert posts(app_client, "redress") == []


def test_a_marked_appeals_card_leaves_out_its_reason(
    app_client, backend, as_handler, token_for
):
    mark(UNPAID)

    conversation, _, _ = ask(token_for, (PAY,))

    card = read(backend, conversation, as_handler)["card"]
    assert card["reason"] is None
    assert card["redress"]["total"] == "556.40"


def test_a_second_payment_in_the_same_reply_is_answered_one_at_a_time(
    app_client, backend, token_for
):
    calls = (PAY, ("pay_redress", {"claim_id": "CLM-1603"}))
    conversation, saver, _ = ask(token_for, calls)

    model = answer(conversation, saver, token_for, True)

    assert len(posts(app_client, "redress")) == 1
    other = backend.get("/api/claims/CLM-1603/appeal").json()
    assert other["redress_payment"] is None
    results = [
        m.content
        for m in model.seen[-1]
        if isinstance(m, ToolMessage) and m.name == "pay_redress"
    ]
    assert any("One payment at a time" in text for text in results)


def test_what_needs_a_handler_has_the_appeals_and_the_redress_waiting(
    app_client, token_for
):
    _, _, model = ask(token_for, (("what_needs_a_handler", {}),))

    needs = tool_json(model, "what_needs_a_handler")
    assert [a["claim_id"] for a in needs["appeals_waiting_for_an_outcome"]] == [
        "CLM-1607",
        "CLM-1608",
    ]
    assert [a["claim_id"] for a in needs["redress_waiting_for_sign_off"]] == [
        "CLM-1602",
        "CLM-1603",
    ]
