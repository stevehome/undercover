import json

import pytest
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from agent import copilot_turns, copilot_waiting
from agent.tests.copilot_helpers import begin, reply, seen_model, tool_call
from conftest import DANA

RUN = {
    "concurrency": 2,
    "model": "stub/model",
    "reasoning_effort": "low",
    "configuration_version": 1,
}
ASK = "Work the queue and tell me what needs me"


def make_run(backend):
    return backend.post("/api/runs/dispatch", json=RUN).json()["run_id"]


def work(model, token_for):
    conversation = begin(DANA, ASK)
    turn = copilot_turns.Turn(
        conversation.conversation_id, token_for(DANA), model, InMemorySaver(), None
    )
    copilot_turns.work_turn(turn, ASK)
    return conversation


def result_of(model, name):
    message = next(
        m for m in model.seen[-1] if isinstance(m, ToolMessage) and m.name == name
    )
    return json.loads(str(message.content))


def test_a_wait_ends_when_the_run_does_with_its_summary(app_client, backend, token_for):
    run_id = make_run(backend)
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 3:
            backend.post(f"/api/runs/{run_id}/finish")

    waited = copilot_waiting.wait_for_run(
        token_for(DANA), run_id, follow_on="the Queue page", sleep=sleep
    )

    assert len(sleeps) == 3
    assert (waited["ended"], waited["status"]) == (True, "finished")
    assert {"approved", "declined", "referred"} <= set(waited["summary"])


def test_after_fifteen_minutes_the_wait_says_the_work_is_still_going(
    app_client, backend, token_for
):
    run_id = make_run(backend)
    clock = [0]

    def sleep(seconds):
        clock[0] += seconds * copilot_waiting.NANOS_PER_SECOND

    waited = copilot_waiting.wait_for_run(
        token_for(DANA),
        run_id,
        follow_on="the Queue page",
        now=lambda: clock[0],
        sleep=sleep,
    )

    assert waited["ended"] is False
    assert clock[0] // copilot_waiting.NANOS_PER_SECOND == (
        copilot_waiting.GIVE_UP_SECONDS
    )
    assert "15 minutes" in waited["message"]
    assert "the Queue page" in waited["message"]
    assert waited["status"] == "running"


def test_a_dispatch_the_app_refuses_passes_on_the_reason(
    app_client, backend, agent_stub, as_handler, token_for
):
    make_run(backend)
    model = seen_model(
        tool_call("start_dispatch", {"agents": 2, "wait": True}), reply("Not now.")
    )

    conversation = work(model, token_for)

    steps = backend.get(
        f"/api/copilot/conversations/{conversation.conversation_id}",
        headers=as_handler(),
    ).json()["steps"]
    assert steps[0]["state"] == "refused"
    assert "already running" in steps[0]["reason"]


@pytest.fixture
def agent_works(agent_stub, backend):
    """A stand-in claim agent that finishes each run it is asked to work at once."""
    agent_stub.on_ask = staticmethod(
        lambda operation, body: backend.post(f"/api/runs/{body['run_id']}/finish")
    )
    return agent_stub


def test_a_waited_dispatch_returns_how_it_ended_with_no_model_call(
    app_client, backend, agent_works, token_for
):
    model = seen_model(
        tool_call("start_dispatch", {"agents": 2, "wait": True}), reply("Done.")
    )

    work(model, token_for)

    started = result_of(model, "start_dispatch")
    assert started["outcome"]["ended"] is True
    assert started["outcome"]["status"] == "finished"
    assert started["agents"] == 2
    assert len(model.seen) == 2


def test_an_evaluation_is_started_with_the_set_and_waited_on(
    app_client, backend, agent_works, token_for
):
    model = seen_model(
        tool_call(
            "start_evaluation",
            {"eval_set": "held_out", "tiny": True, "agents": 3, "wait": True},
        ),
        reply("Done."),
    )

    work(model, token_for)

    started = result_of(model, "start_evaluation")
    run = backend.get(f"/api/runs/{started['run_id']}").json()
    assert (run["kind"], run["eval_set"], run["tiny"], run["concurrency"]) == (
        "evaluation",
        "held_out",
        True,
        3,
    )
    assert started["outcome"]["status"] == "finished"


def test_the_success_criteria_run_the_whole_held_out_set_and_come_from_code(
    app_client, backend, agent_works, token_for
):
    model = seen_model(tool_call("check_success_criteria"), reply("Not yet."))

    work(model, token_for)

    result = result_of(model, "check_success_criteria")
    evaluation = backend.get("/api/evaluations").json()[0]
    assert (evaluation["eval_set"], evaluation["tiny"]) == ("held_out", False)
    straight = result["criteria"][0]
    expected = f"{float(evaluation['measures']['straight_through']) * 100:.1f}%"
    assert straight["figure"] == expected
    assert straight["target"] == "at least 70.0%"
    assert result["criteria"][2]["met"] is True
    assert result["all_met"] is False
    assert len(model.seen) == 2


def test_a_refused_criteria_evaluation_passes_on_the_reason(
    app_client, backend, token_for
):
    make_run(backend)
    model = seen_model(tool_call("check_success_criteria"), reply("Busy."))

    work(model, token_for)

    result = result_of(model, "check_success_criteria")
    first, second, third = result["criteria"]
    assert first["figure"] is None
    assert second["figure"] is None
    assert "already running" in first["note"]
    assert third["met"] is True
    assert result["all_met"] is None
