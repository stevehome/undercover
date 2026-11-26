import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import select

from agent import backend_http, copilot_api, copilot_turns
from agent.copilot_memory import HandlerMemory
from agent.copilot_nodes import MAX_MODEL_CALLS
from agent.copilot_route import ContextOnlyRoute
from agent.direct import DirectRoute
from agent.refusals import BY_APP, Refusal
from agent.tests.copilot_helpers import (
    RecordingClient,
    begin,
    forever,
    reply,
    seen_model,
    tool_call,
)
from agent.tests.stand_in_memory import StandInMemory
from backend import copilot_turns as backend_turns
from backend import db, tables
from conftest import DANA, MARCUS

ASK = "Who needs me today?"


@pytest.fixture
def app_client(monkeypatch):
    """The Copilot's own client to the app: no key, and it keeps what it sends."""
    client = RecordingClient()
    monkeypatch.setattr(backend_http, "client", client)
    return client


@pytest.fixture
def agent_running(agent_stub):
    """A stand-in for the claim agent, so the app can start work."""
    return agent_stub


def work(email, model, token_for, **options):
    """Begin a turn in the app and work it; return its conversation.

    Options: `saver`, `text`, `memory`, and `conversation` to carry one on.
    """
    text = options.get("text", ASK)
    started = options.get("conversation") or begin(email, text)
    sign_in = token_for(email)
    turn = copilot_turns.Turn(
        started.conversation_id,
        sign_in,
        model,
        options.get("saver") or InMemorySaver(),
        options.get("memory"),
    )
    copilot_turns.work_turn(turn, text)
    started.sign_in = sign_in
    return started


def read(backend, conversation, as_handler, email=DANA):
    return backend.get(
        f"/api/copilot/conversations/{conversation.conversation_id}",
        headers=as_handler(email),
    ).json()


def test_a_turn_asks_who_is_signed_in_before_any_model_call(
    app_client, backend, as_handler, token_for
):
    model = seen_model(reply("Nobody."))
    conversation = work(DANA, model, token_for)

    assert app_client.sent[0]["Authorization"] == f"Bearer {conversation.sign_in}"
    seen = read(backend, conversation, as_handler)
    assert (seen["status"], seen["messages"][-1]["text"]) == ("done", "Nobody.")


def test_a_refused_sign_in_ends_the_turn_with_no_call_to_the_model(
    app_client, backend, as_handler
):
    model = seen_model(reply("Never said."))
    conversation = begin(DANA, ASK)

    copilot_turns.work_turn(
        copilot_turns.Turn(
            conversation.conversation_id, "not-a-token", model, InMemorySaver(), None
        ),
        ASK,
    )

    assert next(model.messages) == reply("Never said.")
    assert model.seen == []
    assert read(backend, conversation, as_handler)["status"] == "working"


def test_a_lookup_a_customer_and_an_action_each_make_a_card_that_ends_done(
    app_client, agent_running, backend, as_handler, token_for
):
    model = seen_model(
        tool_call("list_claims", call_id="1"),
        tool_call("find_customers", {"name": "a"}, call_id="2"),
        tool_call("start_dispatch", {"agents": 2}, call_id="3"),
        reply("Started."),
    )

    conversation = work(DANA, model, token_for)

    steps = read(backend, conversation, as_handler)["steps"]
    assert [(s["tool"], s["kind"], s["state"]) for s in steps] == [
        ("list_claims", "claims", "done"),
        ("find_customers", "customers", "done"),
        ("start_dispatch", "action", "done"),
    ]
    assert all(s["seconds"] is not None for s in steps)
    assert steps[1]["input"] == "name: a"
    assert agent_running.calls == ["work_run"]


def test_a_refused_call_is_a_refused_card_and_the_model_reads_the_reason(
    app_client, agent_running, backend, as_handler, token_for
):
    model = seen_model(
        tool_call("start_dispatch", {"agents": 2}, call_id="1"),
        tool_call("start_dispatch", {"agents": 2}, call_id="2"),
        reply("A dispatch is already running."),
    )

    conversation = work(DANA, model, token_for)

    steps = read(backend, conversation, as_handler)["steps"]
    assert [s["state"] for s in steps] == ["done", "refused"]
    assert "already running" in steps[1]["reason"]
    last_read = [m for m in model.seen[-1] if m.type == "tool"][-1]
    assert "Refused by the app" in last_read.content
    assert "already running" in last_read.content


def test_the_agents_count_in_settings_is_used_when_the_handler_names_none(
    app_client, agent_running, backend, token_for
):
    model = seen_model(tool_call("start_dispatch"), reply("Started."))

    work(DANA, model, token_for)

    settings = backend.get("/api/settings").json()
    agents = next(s["value"] for s in settings if s["key"] == "improver_agents_at_once")
    assert backend.get("/api/runs/current").json()["concurrency"] == agents


def test_every_call_to_the_app_carries_the_sign_in_and_never_the_agents_key(
    app_client, agent_running, token_for
):
    model = seen_model(
        tool_call("list_claims", call_id="1"),
        tool_call("get_latest_dispatch", call_id="2"),
        reply("Done."),
    )

    conversation = work(DANA, model, token_for)

    assert app_client.sent
    for headers in app_client.sent:
        assert headers == {"Authorization": f"Bearer {conversation.sign_in}"}


def test_a_context_layer_call_works_and_the_app_target_is_refused():
    route = ContextOnlyRoute(DirectRoute())

    answered = route.call("undercover-context", "get_claim_rules", {})
    with pytest.raises(Refusal) as refusal:
        route.call("undercover-app", "get_claim", {"claim_id": "CLM-1001"})

    assert answered
    assert refusal.value.source == BY_APP


def test_a_context_lookup_is_a_context_card_with_its_files_and_owners(
    app_client, backend, as_handler, token_for
):
    model = seen_model(
        tool_call("get_plan", {"plan": "premium"}),
        reply("Here is the plan."),
    )

    conversation = work(DANA, model, token_for)

    step = read(backend, conversation, as_handler)["steps"][0]
    assert (step["kind"], step["state"], step["reason"]) == ("context", "done", None)
    assert step["files"]
    assert step["files"]["plans.yaml"]["owner"]


def test_the_sign_in_is_in_no_checkpoint_no_step_and_no_log(
    app_client, agent_running, token_for, caplog
):
    saver = InMemorySaver()
    model = seen_model(tool_call("list_claims"), reply("Done."))

    conversation = work(DANA, model, token_for, saver=saver)

    kept = repr(saver.storage) + repr(saver.blobs) + repr(saver.writes)
    assert conversation.sign_in not in kept
    assert conversation.sign_in not in caplog.text
    with db.connection() as conn:
        for table in tables.metadata.sorted_tables:
            for row in conn.execute(select(table)):
                assert conversation.sign_in not in str(row._mapping)


def test_a_turn_stops_at_the_model_call_limit_with_a_failed_turn(
    app_client, backend, as_handler, token_for
):
    model = forever("list_claims")

    conversation = work(DANA, model, token_for)

    seen = read(backend, conversation, as_handler)
    assert seen["status"] == "failed"
    assert str(MAX_MODEL_CALLS) in seen["failure"]
    assert len(model.seen) == MAX_MODEL_CALLS
    assert seen["messages"][-1]["role"] == "copilot"


def test_a_turns_calls_and_cost_are_its_totals(
    app_client, backend, as_handler, token_for
):
    model = seen_model(tool_call("list_claims"), reply("Done."))

    conversation = work(DANA, model, token_for)

    answer = read(backend, conversation, as_handler)["messages"][-1]
    assert answer["model_calls"] == 2
    assert answer["cost"] == "0.000624000"


def test_with_memory_on_the_first_card_is_the_lookup_and_the_turn_saves_two_events(
    app_client, backend, as_handler, token_for
):
    store = StandInMemory()
    store.memories = [(("handlers", "HND-01", "preferences"), "Dana likes tables.")]
    model = seen_model(tool_call("list_claims"), reply("Here you are."))

    conversation = work(DANA, model, token_for, memory=HandlerMemory(store))

    steps = read(backend, conversation, as_handler)["steps"]
    assert (steps[0]["tool"], steps[0]["kind"]) == ("search_memory", "memory")
    assert "Dana likes tables." in steps[0]["result"]
    assert [s["tool"] for s in steps[1:]] == ["list_claims"]
    assert store.searches == [(("handlers", "HND-01"), ASK)]
    assert [(namespace, key) for namespace, key, _ in store.events] == [
        (("HND-01", conversation.conversation_id), "message"),
        (("HND-01", conversation.conversation_id), "answer"),
    ]
    assert [v["message"].content for _, _, v in store.events] == [ASK, "Here you are."]
    assert "Dana likes tables." in model.seen[0][0].content


def test_with_memory_off_there_is_no_card_and_no_save(
    app_client, backend, as_handler, token_for
):
    model = seen_model(reply("Done."))

    conversation = work(DANA, model, token_for)

    assert read(backend, conversation, as_handler)["steps"] == []


def test_another_handlers_memory_is_never_searched(
    app_client, backend, as_handler, token_for
):
    store = StandInMemory()
    store.memories = [(("handlers", "HND-01", "facts"), "Dana watches CLM-1001.")]

    work(MARCUS, seen_model(reply("Done.")), token_for, memory=HandlerMemory(store))

    assert store.searches == [(("handlers", "HND-02"), ASK)]


def test_a_turn_stopped_partway_is_carried_on_with_its_unfinished_calls_answered(
    app_client, backend, as_handler, token_for, monkeypatch
):
    saver = InMemorySaver()

    list_claims = copilot_api.list_claims

    def crash(sign_in):
        raise RuntimeError("boom")

    monkeypatch.setattr(copilot_api, "list_claims", crash)
    first = work(DANA, seen_model(tool_call("list_claims")), token_for, saver=saver)
    assert read(backend, first, as_handler)["status"] == "failed"
    monkeypatch.setattr(copilot_api, "list_claims", list_claims)
    model = seen_model(reply("Back again."))

    second_text = "Try again"
    backend_turns.begin(first.conversation_id, first.handler_id, second_text)
    work(DANA, model, token_for, saver=saver, text=second_text, conversation=first)

    messages = model.seen[0]
    calls = {
        c["id"] for m in messages if isinstance(m, AIMessage) for c in m.tool_calls
    }
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    assert calls == answered == {"1"}
    assert [m.content for m in messages if m.type == "human"] == [ASK, second_text]
    assert read(backend, first, as_handler)["status"] == "done"


def test_a_restart_carries_a_conversation_on_with_all_its_earlier_messages(
    app_client, backend, as_handler, token_for
):
    saver = InMemorySaver()
    first = work(DANA, seen_model(reply("First answer.")), token_for, saver=saver)
    backend_turns.begin(first.conversation_id, first.handler_id, "And then?")
    model = seen_model(reply("Second answer."))

    work(DANA, model, token_for, saver=saver, text="And then?", conversation=first)

    assert [m.content for m in model.seen[0][1:]] == [
        ASK,
        "First answer.",
        "And then?",
    ]
