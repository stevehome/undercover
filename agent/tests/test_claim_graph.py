import pytest
from langchain_core.messages import AIMessage

from agent import agents, api, backend_http
from agent.claim_nodes import MAX_MODEL_CALLS, ModelCallLimit
from agent.tests import records
from agent.tests.conftest import REPLY_USAGE, StubModel

CLAIM = "CLM-1001"


def decision(kind="approve", payout="420.00"):
    """A decision for the scripted model to record; an approval has its calculation."""
    if kind == "approve":
        records.calculated(CLAIM, payout)
    return (
        "decide_claim",
        {
            "decision": kind,
            "payout": payout,
            "reason": "Stubbed.",
            "policy_reference": "Section 3",
        },
    )


def sign_off(backend, as_handler):
    return backend.post(f"/api/claims/{CLAIM}/sign-off", headers=as_handler())


def test_an_approval_over_the_limit_waits_and_a_sign_off_pays_it(
    backend, script, saver, as_handler
):
    agents.decide_claim(CLAIM, script(decision(payout="1200.00"), "Approved."), saver)

    waiting = api.get_claim(CLAIM)
    assert waiting["status"] == "waiting for sign-off"
    assert waiting["paid_amount"] is None
    assert "waiting for a handler" in agents.decide_claim(CLAIM, script(), saver)

    sign_off(backend, as_handler)

    paid = api.get_claim(CLAIM)
    assert (paid["status"], paid["paid_amount"]) == ("decided", "1200.00")
    assert paid["signed_off_by"] == "HND-01"
    texts = [s["text"] for s in backend.get(f"/api/claims/{CLAIM}/steps").json()]
    assert texts[-2:] == [
        "Waiting for a handler to sign off $1200.00",
        "Paid $1200.00",
    ]


def test_an_agent_resumed_after_a_sign_off_finishes_without_paying(
    backend, script, saver, as_handler, monkeypatch
):
    agents.decide_claim(CLAIM, script(decision(payout="1200.00"), "Approved."), saver)
    sign_off(backend, as_handler)
    paid = api.get_claim(CLAIM)["paid_on"]
    asked = []
    send = backend_http.send
    monkeypatch.setattr(
        backend_http,
        "send",
        lambda method, path, **kw: asked.append(path) or send(method, path, **kw),
    )

    agents.decide_claim(CLAIM, script(), saver)

    assert not any(path.endswith("/payment") for path in asked)
    assert api.get_claim(CLAIM)["paid_on"] == paid
    texts = [s["text"] for s in backend.get(f"/api/claims/{CLAIM}/steps").json()]
    assert "Signed off by HND-01" in texts


@pytest.mark.parametrize("kind", ["decline", "refer"])
def test_a_decline_or_referral_is_not_paid(backend, script, saver, kind):
    agents.decide_claim(CLAIM, script(decision(kind, "0.00"), "Done."), saver)

    claim = api.get_claim(CLAIM)
    assert (claim["status"], claim["paid_amount"]) == ("decided", None)


def test_deciding_twice_is_a_repeat_not_a_second_decision(backend, script, saver):
    llm = script(decision(), decision(), "Done.")

    agents.decide_claim(CLAIM, llm, saver)

    claim = api.get_claim(CLAIM)
    assert claim["decision"] == "approve"
    steps = backend.get(f"/api/claims/{CLAIM}/steps").json()
    assert len([s for s in steps if s["text"].startswith("Decided")]) == 2


def test_a_refusal_goes_back_to_the_model(backend, script, saver):
    bad = ("read_section", {"document": "claims_manual", "number": 99})

    agents.decide_claim(CLAIM, script(bad, decision(), "Done."), saver)

    assert api.get_claim(CLAIM)["paid_amount"] == "420.00"
    steps = backend.get(f"/api/claims/{CLAIM}/steps").json()
    assert any(s["text"].startswith("Refused by the context layer:") for s in steps)


def test_no_decision_sends_the_claim_back_to_the_agent(backend, script, saver):
    agents.decide_claim(CLAIM, script("I think so.", decision(), "Done."), saver)

    assert api.get_claim(CLAIM)["decision"] == "approve"


def test_a_model_that_never_stops_fails_the_claim(backend, script, saver):
    steps = [("get_claim", {})] * (MAX_MODEL_CALLS + 1)

    with pytest.raises(ModelCallLimit):
        agents.decide_claim(CLAIM, script(*steps), saver)


class Stopped(BaseException):
    """Stands for a crash, a kill or Ctrl-C, which no `except Exception` catches."""


def stops_after_reading_the_claim():
    """A stub model that reads the claim, then is stopped."""
    call = AIMessage(
        content="",
        tool_calls=[{"name": "get_claim", "args": {}, "id": "1"}],
        response_metadata=REPLY_USAGE,
    )
    yield call
    raise Stopped


def test_a_stopped_claim_carries_on_from_its_last_step(backend, script, saver):
    with pytest.raises(Stopped):
        agents.decide_claim(
            CLAIM, StubModel(messages=stops_after_reading_the_claim()), saver
        )

    assert api.get_claim(CLAIM)["status"] == "in progress"
    agents.decide_claim(CLAIM, script(decision(), "Done."), saver)

    claim = api.get_claim(CLAIM)
    assert (claim["thread"], claim["paid_amount"]) == (1, "420.00")
    steps = [s["text"] for s in backend.get(f"/api/claims/{CLAIM}/steps").json()]
    assert steps.count("Decided: approve for $420.00") == 1
    assert (
        steps.count("Read the claim, its policy and the customer's claim history") == 1
    )
