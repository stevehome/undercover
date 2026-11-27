import pytest
from sqlalchemy import update

from backend import copilot_turns, db, model_used, tables
from backend.tests import records
from conftest import API_KEY, MARCUS

ASK = "Who needs me today?"


def make(client):
    return client.post("/api/copilot/conversations").json()["conversation_id"]


def ask(client, conversation_id, text=ASK):
    return client.post(
        f"/api/copilot/conversations/{conversation_id}/messages", json={"text": text}
    )


def read(client, conversation_id):
    return client.get(f"/api/copilot/conversations/{conversation_id}").json()


def done(client, conversation_id, text="Nobody."):
    return client.post(
        f"/api/copilot/conversations/{conversation_id}/done",
        json={"text": text, "model_calls": 2, "cost_nanos": 1500000, "work_ms": 2500},
    )


def age_the_turn(conversation_id, seconds):
    columns = tables.copilot_conversations.c
    with db.connection() as conn:
        conn.execute(
            update(tables.copilot_conversations)
            .where(columns.conversation_id == conversation_id)
            .values(turn_started_on=db.now(-seconds))
        )


def test_a_message_starts_a_turn_with_the_model_and_the_sign_in_and_no_key(
    client, copilot_stub
):
    conversation_id = make(client)

    assert ask(client, conversation_id).status_code == 202

    model, effort = model_used.for_copilot()
    token = client.headers["Authorization"].removeprefix("Bearer ")
    assert copilot_stub.payloads == [
        {
            "operation": "start_turn",
            "conversation_id": conversation_id,
            "message": ASK,
            "sign_in": token,
            "model": model,
            "reasoning_effort": effort,
        }
    ]
    assert copilot_stub.authorizations == [None]
    seen = read(client, conversation_id)
    assert (seen["title"], seen["status"]) == (ASK, "working")
    assert [(m["role"], m["text"]) for m in seen["messages"]] == [("handler", ASK)]


def test_a_second_message_while_a_turn_works_is_a_409(client, copilot_stub):
    conversation_id = make(client)
    ask(client, conversation_id)

    second = ask(client, conversation_id, "And?")

    assert second.status_code == 409
    assert len(copilot_stub.payloads) == 1


def test_a_turn_working_for_twenty_minutes_reads_as_stopped_and_takes_a_message(
    client, copilot_stub
):
    conversation_id = make(client)
    ask(client, conversation_id)
    age_the_turn(conversation_id, copilot_turns.TURN_SECONDS + 5)

    assert read(client, conversation_id)["status"] == "stopped"
    assert ask(client, conversation_id, "Again").status_code == 202


def test_a_turn_waiting_for_a_confirmation_is_never_stopped_and_refuses_a_message(
    client, copilot_stub
):
    conversation_id = make(client)
    ask(client, conversation_id)
    card = {"claim_id": "CLM-1001", "payout": "1200.00"}
    client.post(
        f"/api/copilot/conversations/{conversation_id}/waiting", json={"card": card}
    )
    age_the_turn(conversation_id, copilot_turns.TURN_SECONDS + 5)

    seen = read(client, conversation_id)
    refused = ask(client, conversation_id, "Hello?")

    assert (seen["status"], seen["card"]) == ("waiting for a confirmation", card)
    assert refused.status_code == 409
    assert "confirmation" in refused.json()["detail"]


def test_a_turn_the_copilot_refuses_is_undone_with_its_reason(client, copilot_stub):
    copilot_stub.refuse = True
    conversation_id = make(client)

    refused = ask(client, conversation_id)

    assert (refused.status_code, refused.json()["detail"]) == (
        409,
        "The Copilot is busy",
    )
    seen = read(client, conversation_id)
    assert (seen["status"], seen["messages"], seen["title"]) == ("done", [], None)


def test_a_turn_the_copilot_never_took_is_undone(client, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_COPILOT", "http://127.0.0.1:9")
    conversation_id = make(client)

    refused = ask(client, conversation_id)

    assert refused.status_code == 503
    assert read(client, conversation_id)["status"] == "done"


def test_steps_arrive_working_then_done_refused_or_failed_in_order(
    client, copilot_stub
):
    conversation_id = make(client)
    ask(client, conversation_id)
    steps = f"/api/copilot/conversations/{conversation_id}/steps"
    first = client.post(
        steps, json={"tool": "list_claims", "kind": "claims", "input": "the queue"}
    ).json()["step_id"]
    second = client.post(
        steps, json={"tool": "start_dispatch", "kind": "action", "input": "10 agents"}
    ).json()["step_id"]

    assert [
        (s["tool"], s["state"]) for s in read(client, conversation_id)["steps"]
    ] == [
        ("list_claims", "working"),
        ("start_dispatch", "working"),
    ]
    client.post(
        f"/api/copilot/steps/{first}/finish",
        json={"state": "done", "result": "x" * 5000},
    )
    client.post(
        f"/api/copilot/steps/{second}/finish",
        json={"state": "refused", "result": "", "reason": "A run is already going"},
    )

    shown = read(client, conversation_id)["steps"]
    assert [s["state"] for s in shown] == ["done", "refused"]
    assert len(shown[0]["result"]) < 2000
    assert shown[0]["seconds"] is not None
    assert shown[1]["reason"] == "A run is already going"
    assert (
        client.post(
            f"/api/copilot/steps/{first}/finish", json={"state": "done", "result": ""}
        ).status_code
        == 409
    )


def test_a_waiting_confirmation_keeps_its_card_until_answered(client, copilot_stub):
    conversation_id = make(client)
    ask(client, conversation_id)
    card = {"claim_id": "CLM-1001", "payout": "1200.00"}
    client.post(
        f"/api/copilot/conversations/{conversation_id}/waiting", json={"card": card}
    )

    assert read(client, conversation_id)["card"] == card
    assert read(client, conversation_id)["card"] == card

    answered = client.post(
        f"/api/copilot/conversations/{conversation_id}/confirmation",
        json={"confirmed": True},
    )

    assert answered.status_code == 202
    assert copilot_stub.payloads[-1]["operation"] == "answer_confirmation"
    assert copilot_stub.payloads[-1]["confirmed"] is True
    assert copilot_stub.payloads[-1]["card"] == card
    seen = read(client, conversation_id)
    assert (seen["status"], seen["card"]) == ("working", None)


def test_a_confirmation_the_copilot_refuses_goes_back_to_waiting(client, copilot_stub):
    conversation_id = make(client)
    ask(client, conversation_id)
    card = {"claim_id": "CLM-1001"}
    client.post(
        f"/api/copilot/conversations/{conversation_id}/waiting", json={"card": card}
    )
    copilot_stub.refuse = True

    answered = client.post(
        f"/api/copilot/conversations/{conversation_id}/confirmation",
        json={"confirmed": False},
    )

    assert answered.status_code == 409
    seen = read(client, conversation_id)
    assert (seen["status"], seen["card"]) == ("waiting for a confirmation", card)


def test_an_answer_ends_the_turn_with_its_usage(client, copilot_stub):
    conversation_id = make(client)
    ask(client, conversation_id)

    assert done(client, conversation_id).status_code == 200

    seen = read(client, conversation_id)
    answer = seen["messages"][-1]
    assert seen["status"] == "done"
    assert (answer["role"], answer["text"], answer["model_calls"]) == (
        "copilot",
        "Nobody.",
        2,
    )
    assert (answer["cost"], answer["seconds"]) == ("0.001500000", 2.5)
    assert done(client, conversation_id).status_code == 409


def test_a_failed_turn_ends_with_a_short_message_and_the_handler_can_ask_again(
    client, copilot_stub
):
    conversation_id = make(client)
    ask(client, conversation_id)

    client.post(
        f"/api/copilot/conversations/{conversation_id}/failed",
        json={"reason": "The model stopped answering"},
    )

    seen = read(client, conversation_id)
    assert (seen["status"], seen["failure"]) == (
        "failed",
        "The model stopped answering",
    )
    assert "The model stopped answering" in seen["messages"][-1]["text"]
    assert ask(client, conversation_id, "Try again").status_code == 202


def test_another_handlers_conversation_is_a_403_for_everything(
    client, copilot_stub, as_handler
):
    conversation_id = make(client)
    ask(client, conversation_id)
    client.headers.update(as_handler(MARCUS))
    base = f"/api/copilot/conversations/{conversation_id}"

    responses = [
        client.get(base),
        client.post(f"{base}/messages", json={"text": "hi"}),
        client.post(f"{base}/confirmation", json={"confirmed": True}),
        client.post(
            f"{base}/done",
            json={"text": "x", "model_calls": 1, "cost_nanos": 1, "work_ms": 1},
        ),
    ]

    assert [r.status_code for r in responses] == [403, 403, 403, 403]
    assert client.get("/api/copilot/conversations").json() == []


def test_a_conversation_that_does_not_exist_is_a_404(client):
    assert client.get("/api/copilot/conversations/copilot-nothing").status_code == 404


def test_the_conversations_are_listed_newest_first_by_their_first_question(
    client, copilot_stub
):
    first = make(client)
    ask(client, first, "First question")
    second = make(client)
    ask(client, second, "Second question " + "word " * 30)

    listed = client.get("/api/copilot/conversations").json()

    assert [c["conversation_id"] for c in listed] == [second, first]
    assert listed[1]["title"] == "First question"
    assert len(listed[0]["title"]) <= copilot_turns.TITLE_LENGTH


def test_the_sign_in_is_in_no_table_after_a_turn(client, copilot_stub):
    token = client.headers["Authorization"].removeprefix("Bearer ")
    conversation_id = make(client)
    ask(client, conversation_id)
    done(client, conversation_id)

    with db.connection() as conn:
        for table in tables.metadata.sorted_tables:
            for row in conn.execute(table.select()):
                assert token not in str(row._mapping)


def test_the_health_check_asks_the_copilot(client, copilot_stub):
    assert client.get("/api/copilot/health").json() == {"healthy": True}
    assert copilot_stub.payloads == [{"operation": "health"}]


def test_customers_are_found_by_part_of_a_name_in_any_case_and_by_id(client):
    owner = client.get("/api/claims/CLM-1001").json()["customer_id"]
    customer = client.get(f"/api/customers/{owner}").json()
    part = customer["name"].split()[0][1:4].upper()

    found = client.get("/api/customers", params={"name": part}).json()

    assert owner in [c["customer_id"] for c in found]
    assert all(part.lower() in c["name"].lower() for c in found)
    assert {"policies", "claims_in_queue", "previous_claims"} <= set(customer)
    assert "CLM-1001" in [c["claim_id"] for c in customer["claims_in_queue"]]
    assert client.get("/api/customers/NOBODY").status_code == 404
    assert client.get("/api/customers", params={"name": "%"}).json() == []


def test_a_policy_comes_with_the_limits_of_its_plan(client):
    claim = client.get("/api/claims/CLM-1001").json()

    policy = client.get(f"/api/policies/{claim['policy_id']}").json()

    assert policy["policy_id"] == claim["policy_id"]
    assert "baggage_max" in policy["plan_limits"]


def test_the_evaluations_give_measures_and_never_a_handlers_decision(client):
    for eval_set in ("held_out", "evaluation"):
        client.post(
            "/api/runs/evaluation",
            json={
                "concurrency": 5,
                "eval_set": eval_set,
                "tiny": True,
                "model": "stub/model",
                "reasoning_effort": "low",
                "configuration_version": 1,
            },
        )
        client.post(f"/api/runs/{1 if eval_set == 'held_out' else 2}/finish")

    shown = client.get("/api/copilot/evaluations").json()

    assert [e["eval_set"] for e in shown] == ["evaluation", "held_out"]
    assert {"accuracy", "straight_through"} <= set(shown[0]["measures"])
    for banned in ("handler_decision", "key_decision", "handler_payout", "claims"):
        assert banned not in str(shown)


OVER = {
    "decision": "approve",
    "payout": "1200.00",
    "reason": "Stubbed.",
    "policy_reference": "Section 3",
}


def test_over_the_limit_counts_the_seeded_earlier_claim(client):
    shown = client.get("/api/payments/over-limit").json()

    assert (shown["paid_over_the_limit"], shown["with_a_sign_off"]) == (1, 1)


def test_over_the_limit_counts_a_paid_sign_off_and_a_payment_without_one(client):
    records.decide(client, "CLM-1001", OVER)
    client.post("/api/claims/CLM-1001/sign-off")
    with db.connection() as conn:
        conn.execute(
            update(tables.claims)
            .where(tables.claims.c.claim_id == "CLM-1002")
            .values(paid_cents=150000, status="decided")
        )

    shown = client.get("/api/payments/over-limit").json()

    assert (shown["paid_over_the_limit"], shown["with_a_sign_off"]) == (3, 2)
    assert {c["claim_id"]: c["signed_off_by"] for c in shown["claims"]} == {
        "CLM-1001": "HND-01",
        "CLM-1002": None,
        "CLM-1606": "HND-01",
    }


def test_what_needs_a_handler_groups_held_referred_and_sent_back_claims(client):
    records.decide(client, "CLM-1001", OVER)
    refer = {**OVER, "decision": "refer", "payout": "0.00"}
    records.decide(client, "CLM-1002", refer)
    records.decide(client, "CLM-1003", OVER)
    client.post("/api/claims/CLM-1003/send-back", json={"note": "Check the receipt"})

    shown = client.get("/api/queue/needs-a-handler").json()

    assert [c["claim_id"] for c in shown["held_for_sign_off"]] == ["CLM-1001"]
    assert [c["claim_id"] for c in shown["referred_or_left_for_a_handler"]] == [
        "CLM-1002"
    ]
    assert [c["claim_id"] for c in shown["sent_back_not_yet_worked"]] == ["CLM-1003"]


NEW_ROUTES = [
    ("get", "/api/copilot/health"),
    ("post", "/api/copilot/conversations"),
    ("get", "/api/copilot/conversations"),
    ("get", "/api/copilot/conversations/copilot-x"),
    ("post", "/api/copilot/conversations/copilot-x/messages"),
    ("post", "/api/copilot/conversations/copilot-x/confirmation"),
    ("post", "/api/copilot/conversations/copilot-x/steps"),
    ("post", "/api/copilot/steps/1/finish"),
    ("post", "/api/copilot/conversations/copilot-x/waiting"),
    ("post", "/api/copilot/conversations/copilot-x/done"),
    ("post", "/api/copilot/conversations/copilot-x/failed"),
    ("get", "/api/copilot/evaluations"),
    ("get", "/api/customers?name=a"),
    ("get", "/api/customers/CUS-1"),
    ("get", "/api/policies/POL-1"),
    ("get", "/api/payments/over-limit"),
    ("get", "/api/queue/needs-a-handler"),
]


@pytest.mark.parametrize(("method", "path"), NEW_ROUTES)
def test_every_new_route_needs_a_handlers_sign_in_not_the_agents_key(
    anonymous, agent, method, path
):
    assert getattr(anonymous, method)(path).status_code == 401
    assert getattr(agent, method)(path).status_code == 401


def test_the_agents_own_api_still_has_exactly_its_four_operations(agent):
    document = agent.get("/api/agent/openapi.json").json()

    assert {
        operation["operationId"]
        for path in document["paths"].values()
        for operation in path.values()
    } == {"get_claim", "calculate_payout", "decide_claim", "pay_claim"}
    assert API_KEY
