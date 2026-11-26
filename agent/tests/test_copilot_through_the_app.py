import threading
import time

import pytest
import uvicorn
from langgraph.checkpoint.memory import InMemorySaver

from agent import checkpoint, copilot_entrypoint, copilot_readiness, harness
from agent.tests.copilot_helpers import reply, seen_model, tool_call


@pytest.fixture
def copilot_server(monkeypatch, app_client):
    """The Copilot's AgentCore app served on a local port with a stub model, and the
    app pointed at it, as `npm run dev` points it at the one on 8081."""
    saver = InMemorySaver()
    monkeypatch.setattr(checkpoint, "saver", lambda: saver)
    copilot_readiness.forget()
    server = uvicorn.Server(
        uvicorn.Config(
            copilot_entrypoint.app, host="127.0.0.1", port=0, log_level="warning"
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    monkeypatch.setenv("UNDERCOVER_COPILOT", f"http://127.0.0.1:{port}")
    yield
    server.should_exit = True
    thread.join()
    copilot_readiness.forget()


def wait_for_the_answer(backend, conversation_id):
    for _ in range(500):
        seen = backend.get(f"/api/copilot/conversations/{conversation_id}").json()
        if seen["status"] != "working":
            return seen
        time.sleep(0.02)
    raise AssertionError("The turn never ended")


def test_a_message_starts_a_turn_on_the_copilots_app_and_its_steps_and_answer_come_back(
    copilot_server, backend, monkeypatch
):
    model = seen_model(tool_call("list_claims"), reply("The queue has claims."))
    monkeypatch.setattr(harness, "copilot_model", lambda name, effort: model)
    conversation_id = backend.post("/api/copilot/conversations").json()[
        "conversation_id"
    ]

    sent = backend.post(
        f"/api/copilot/conversations/{conversation_id}/messages",
        json={"text": "What is in the queue?"},
    )

    assert sent.status_code == 202
    seen = wait_for_the_answer(backend, conversation_id)
    assert seen["status"] == "done"
    assert [(s["tool"], s["state"]) for s in seen["steps"]] == [("list_claims", "done")]
    assert [m["text"] for m in seen["messages"]] == [
        "What is in the queue?",
        "The queue has claims.",
    ]
    assert seen["messages"][-1]["model_calls"] == 2
