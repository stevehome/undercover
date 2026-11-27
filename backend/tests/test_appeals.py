import pytest
from sqlalchemy import insert, select

from backend import appeal_figures, appeals, db, tables
from backend.tests import records
from conftest import API_KEY, MARCUS

GROUNDS = "The ferry was late and I could not use the hotel I had paid for."
APPEAL = {
    "ombudsman_reference": "OMB-2026-50001",
    "received_on": "2026-11-20",
    "grounds": GROUNDS,
}
UPHELD = {
    "outcome": "upheld",
    "decided_on": "2026-11-25",
    "reason": "The wording was unclear about the hotel.",
    "claim_amount": "120.00",
    "compensation": "50.00",
    "interest": "1.50",
}
NOT_UPHELD = {
    "outcome": "not upheld",
    "decided_on": "2026-11-25",
    "reason": "The insurer applied the exclusion fairly.",
    "claim_amount": "0.00",
    "compensation": "0.00",
    "interest": "0.00",
}
DECLINE = {
    "decision": "decline",
    "payout": "0.00",
    "reason": "Not covered.",
    "policy_reference": "Section 9",
}
APPROVE = {**DECLINE, "decision": "approve", "payout": "420.00"}
REFER = {**DECLINE, "decision": "refer"}
OVER = {**APPROVE, "payout": "1200.00"}


def appeal_url(claim_id, tail=""):
    return f"/api/claims/{claim_id}/appeal{tail}"


def declined(client, claim_id="CLM-1001"):
    records.decide(client, claim_id, DECLINE)
    return claim_id


def appealed(client, check, claim_id="CLM-1001"):
    declined(client, claim_id)
    response = client.post(appeal_url(claim_id), json=APPEAL)
    assert response.status_code == 200, response.text
    return claim_id


def test_an_appeal_is_recorded_on_a_declined_claim_and_its_text_checked(client, check):
    declined(client)

    response = client.post(appeal_url("CLM-1001"), json=APPEAL)

    appeal = response.json()
    assert response.status_code == 200
    assert (appeal["status"], appeal["label"]) == ("with the ombudsman", "appeal open")
    assert appeal["recorded_by"] == "Dana Whitfield"
    assert appeal["grounds"] == GROUNDS
    assert (appeal["flagged"], appeal["check_cost"]) == (False, "0.000020000")
    assert appeal["claim"]["customer"]["name"]
    assert GROUNDS in check.calls[0]["messages"][1]["content"]


def test_an_appeal_is_recorded_on_an_approved_and_paid_claim(client, check):
    records.decide(client, "CLM-1001", APPROVE)
    client.post("/api/claims/CLM-1001/payment", json={"amount": "420.00"})

    response = client.post(appeal_url("CLM-1001"), json=APPEAL)

    assert response.status_code == 200


def test_a_claim_without_a_final_decision_has_no_appeal(client, check):
    records.decide(client, "CLM-1001", OVER)
    records.decide(client, "CLM-1002", REFER)
    refused = {
        claim: client.post(appeal_url(claim), json=APPEAL)
        for claim in ("CLM-1001", "CLM-1002", "CLM-1003")
    }

    assert {c: r.status_code for c, r in refused.items()} == dict.fromkeys(refused, 409)
    assert "waiting for sign-off" in refused["CLM-1001"].json()["detail"]
    assert "referred" in refused["CLM-1002"].json()["detail"]
    assert "waiting" in refused["CLM-1003"].json()["detail"]
    assert check.calls == []


def test_a_claim_has_at_most_one_appeal(client, check):
    appealed(client, check)

    again = client.post(appeal_url("CLM-1001"), json=APPEAL)

    assert again.status_code == 409
    assert "already has an appeal" in again.json()["detail"]
    assert len(check.calls) == 1


def test_an_unknown_claim_has_no_appeal(client, check):
    assert client.post(appeal_url("CLM-9999"), json=APPEAL).status_code == 404
    assert client.get(appeal_url("CLM-9999")).status_code == 404
    assert client.get(appeal_url("CLM-1001")).json() is None


@pytest.mark.parametrize(
    "change",
    [
        {"grounds": "   "},
        {"ombudsman_reference": ""},
        {"received_on": "yesterday"},
        {"grounds": "x" * 2001},
    ],
)
def test_an_appeal_needs_its_grounds_reference_and_date(client, check, change):
    declined(client)

    response = client.post(appeal_url("CLM-1001"), json={**APPEAL, **change})

    assert response.status_code == 422
    assert check.calls == []


def test_an_appeal_whose_text_has_an_instruction_is_marked_all_the_same(client, check):
    declined(client)
    check.found, check.reason = True, "It tells the assistant to approve in full."

    appeal = client.post(appeal_url("CLM-1001"), json=APPEAL).json()

    assert appeal["flagged"] is True
    assert appeal["flag_reason"] == "It tells the assistant to approve in full."
    assert appeal["grounds"] == GROUNDS


def test_when_the_check_cannot_answer_nothing_is_saved(client, check):
    declined(client)
    check.unreadable = True

    response = client.post(appeal_url("CLM-1001"), json=APPEAL)

    assert response.status_code == 503
    assert client.get(appeal_url("CLM-1001")).json() is None


def test_an_upheld_outcome_keeps_its_three_amounts(client, check):
    appealed(client, check)

    appeal = client.post(appeal_url("CLM-1001", "/outcome"), json=UPHELD).json()

    assert (appeal["status"], appeal["label"]) == (
        "upheld",
        "appeal upheld, redress waiting",
    )
    assert appeal["redress"] == {
        "claim_amount": "120.00",
        "compensation": "50.00",
        "interest": "1.50",
        "total": "171.50",
    }
    assert appeal["outcome_recorded_by"] == "Dana Whitfield"
    assert appeal["check_cost"] == "0.000040000"


def test_a_not_upheld_outcome_has_no_redress(client, check):
    appealed(client, check)

    appeal = client.post(appeal_url("CLM-1001", "/outcome"), json=NOT_UPHELD).json()

    assert (appeal["label"], appeal["redress"]) == ("appeal not upheld", None)


@pytest.mark.parametrize(
    "body",
    [
        {**UPHELD, "claim_amount": "0.00", "compensation": "0.00", "interest": "0.00"},
        {**NOT_UPHELD, "interest": "1.00"},
        {**UPHELD, "outcome": "with the ombudsman"},
        {**UPHELD, "decided_on": "soon"},
        {**UPHELD, "reason": " "},
        {**UPHELD, "interest": "-1.00"},
    ],
)
def test_an_outcome_must_fit_its_redress(client, check, body):
    appealed(client, check)

    response = client.post(appeal_url("CLM-1001", "/outcome"), json=body)

    assert response.status_code == 422
    assert len(check.calls) == 1


def test_an_outcome_is_recorded_once_and_only_on_an_appeal(client, check):
    appealed(client, check)
    client.post(appeal_url("CLM-1001", "/outcome"), json=NOT_UPHELD)

    again = client.post(appeal_url("CLM-1001", "/outcome"), json=UPHELD)
    none = client.post(appeal_url("CLM-1002", "/outcome"), json=UPHELD)

    assert (again.status_code, none.status_code) == (409, 404)


def test_the_reason_is_checked_and_marks_an_appeal_the_grounds_did_not(client, check):
    appealed(client, check)
    check.found, check.reason = True, "It tells the assistant to pay."

    appeal = client.post(appeal_url("CLM-1001", "/outcome"), json=UPHELD).json()

    assert (appeal["flagged"], appeal["flag_reason"]) == (
        True,
        "It tells the assistant to pay.",
    )


def test_a_handler_who_cannot_sign_off_is_refused_redress_with_the_reason(
    client, anonymous, as_handler, check
):
    appealed(client, check)
    client.post(appeal_url("CLM-1001", "/outcome"), json=UPHELD)

    refused = anonymous.post(
        appeal_url("CLM-1001", "/redress"), headers=as_handler(MARCUS)
    )

    assert refused.status_code == 403
    assert "Marcus Oyelaran" in refused.json()["detail"]
    assert client.get(appeal_url("CLM-1001")).json()["redress_payment"] is None


def test_a_senior_handler_pays_redress_once_from_the_recorded_amounts(client, check):
    appealed(client, check)
    client.post(appeal_url("CLM-1001", "/outcome"), json=UPHELD)
    before = client.get("/api/claims/CLM-1001").json()

    paid = client.post(appeal_url("CLM-1001", "/redress"))
    again = client.post(appeal_url("CLM-1001", "/redress"))

    appeal = paid.json()
    assert paid.status_code == 200
    assert appeal["label"] == "appeal upheld, redress paid"
    assert appeal["redress_payment"]["amount"] == "171.50"
    assert appeal["redress_payment"]["signed_off_by"] == "Dana Whitfield"
    assert again.status_code == 409
    assert client.get("/api/claims/CLM-1001").json() == {
        **before,
        "customer_appeals": client.get("/api/claims/CLM-1001").json()[
            "customer_appeals"
        ],
    }


@pytest.mark.parametrize("body", [NOT_UPHELD, None])
def test_there_is_no_redress_to_pay_unless_upheld(client, check, body):
    appealed(client, check)
    if body:
        client.post(appeal_url("CLM-1001", "/outcome"), json=body)

    assert client.post(appeal_url("CLM-1001", "/redress")).status_code == 409


ROUTES = [
    ("post", appeal_url("CLM-1001"), APPEAL),
    ("post", appeal_url("CLM-1001", "/outcome"), UPHELD),
    ("post", appeal_url("CLM-1001", "/redress"), None),
    ("get", appeal_url("CLM-1001"), None),
    ("get", "/api/appeals", None),
    ("get", "/api/appeals/figures", None),
    ("get", "/api/copilot/appeals", None),
    ("get", "/api/copilot/appeals/CLM-1601", None),
]


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
def test_every_appeal_route_needs_a_handlers_sign_in_not_the_agents_key(
    anonymous, agent, method, path, body
):
    for caller in (anonymous, agent):
        assert (
            getattr(caller, method)(
                path, **({"json": body} if body else {})
            ).status_code
            == 401
        )
    assert API_KEY


def test_the_agents_own_api_does_not_gain_an_appeal_operation(agent):
    document = agent.get("/api/agent/openapi.json").json()

    assert {
        operation["operationId"]
        for path in document["paths"].values()
        for operation in path.values()
    } == {"get_claim", "calculate_payout", "decide_claim", "pay_claim"}


def test_the_claim_agent_reads_one_line_for_each_appeal_and_no_text(agent):
    claim = agent.get("/api/claims/CLM-1601").json()

    assert claim["customer_appeals"] == [
        {"claim_id": "CLM-1601", "outcome": "upheld", "decided_on": "2026-11-03"}
    ]
    text = agent.get("/api/claims/CLM-1601").text
    assert "I don't accept that it is" not in text
    assert "does not clearly tell a customer" not in text


def test_a_model_never_reads_a_marked_appeals_text(client, check):
    declined(client)
    check.found, check.reason = True, "It tells the assistant to approve."
    client.post(appeal_url("CLM-1001"), json=APPEAL)
    declined(client, "CLM-1002")
    check.found = False
    client.post(appeal_url("CLM-1002"), json=APPEAL)

    marked = client.get("/api/copilot/appeals/CLM-1001").json()
    plain = client.get("/api/copilot/appeals/CLM-1002").json()
    whole = client.get(appeal_url("CLM-1001")).json()
    listed = {a["claim_id"]: a for a in client.get("/api/copilot/appeals").json()}

    assert (marked["grounds"], marked["text_withheld"]) == (None, True)
    assert marked["flag_reason"] == "It tells the assistant to approve."
    assert plain["grounds"] == GROUNDS
    assert whole["grounds"] == GROUNDS
    assert listed["CLM-1001"]["grounds"] is None
    assert GROUNDS not in str(marked)


def test_the_list_has_every_appeal_newest_received_first(client):
    listed = client.get("/api/appeals").json()

    assert len(listed) == 8
    assert listed[0]["claim_id"] == "CLM-1608"
    assert listed[0]["claim"]["plan"]
    assert [a["received_on"] for a in listed] == sorted(
        (a["received_on"] for a in listed), reverse=True
    )


def test_the_figures_are_worked_out_from_the_records(client):
    figures = client.get("/api/appeals/figures").json()

    assert figures == {
        "open": 2,
        "upheld": 3,
        "not_upheld": 3,
        "upheld_share": "0.5000",
        "redress_paid": "217.10",
        "redress_waiting": "901.50",
    }


def test_the_upheld_share_is_none_while_nothing_is_decided(client):
    with db.connection() as conn:
        conn.execute(tables.appeals.delete())

    figures = appeal_figures.get()

    assert figures["upheld_share"] is None
    assert (figures["open"], figures["upheld"]) == (0, 0)


def test_what_needs_a_handler_has_the_appeals_and_the_redress_waiting(client):
    needs = client.get("/api/queue/needs-a-handler").json()

    assert [a["claim_id"] for a in needs["appeals_waiting_for_an_outcome"]] == [
        "CLM-1607",
        "CLM-1608",
    ]
    waiting = needs["redress_waiting_for_sign_off"]
    assert [(a["claim_id"], a["redress"]) for a in waiting] == [
        ("CLM-1602", "556.40"),
        ("CLM-1603", "345.10"),
    ]


def test_an_evaluations_claim_cannot_be_appealed(client, check):
    with db.connection() as conn:
        copy = dict(
            conn.execute(
                select(tables.claims).where(tables.claims.c.claim_id == "CLM-1601")
            )
            .one()
            ._mapping
        )
        copy.update(claim_id="CLM-1601-E1", evaluation_run_id=1)
        conn.execute(insert(tables.claims).values(**copy))

    response = client.post(appeal_url("CLM-1601-E1"), json=APPEAL)

    assert response.status_code == 409
    assert "evaluation" in response.json()["detail"]


def test_two_appeals_racing_for_a_claim_leave_one_and_a_conflict(
    client, check, monkeypatch
):
    appealed(client, check)
    monkeypatch.setattr(appeals, "find", lambda claim_id: None)

    response = client.post(appeal_url("CLM-1001"), json=APPEAL)

    assert response.status_code == 409
