"""The UnderCover Agent: decides one claim, or carries it on."""

from contextvars import Context
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command

from agent import api, checkpoint, lease, timing, tracing
from agent.claim_graph import build_graph
from agent.claim_state import new_claim
from agent.contexts import ClaimContext
from agent.harness import model


def decide_claim(
    claim_id: str,
    llm: BaseChatModel | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    run_id: int | None = None,
) -> str:
    """Work a claim through its graph: from the start, or from where it stopped.

    `run_id` is the run the work and its cost are recorded with, if any.

    It runs in a fresh context, so a claim worked in a dispatch has a trace of
    its own, tagged with the run.

    A claim waiting at its sign-off carries on only once a handler has signed off.
    A claim another agent is working is left to that agent.
    """
    with lease.held(claim_id) as free:
        if not free:
            return f"{claim_id} is being worked by another agent."
        claim = api.get_claim(claim_id)
        thread_id = f"{claim_id}-{claim['thread']}"
        graph = build_graph(
            checkpointer or checkpoint.saver(),
            llm or model(),
            api.claim_instructions(),
        )
        return Context().run(_work_traced, graph, claim, thread_id, run_id)


def _work_traced(
    graph: Any, claim: dict[str, Any], thread_id: str, run_id: int | None
) -> str:
    """Work a claim in a trace of its own, in one Langfuse session."""
    tags = [] if run_id is None else [f"run-{run_id}"]
    with tracing.trace(thread_id, tags) as traced:
        config: RunnableConfig = {**traced, "configurable": {"thread_id": thread_id}}
        return _work(graph, config, claim, run_id)


def _work(
    graph: Any, config: RunnableConfig, claim: dict[str, Any], run_id: int | None
) -> str:
    """Start the claim's graph, carry it on, or answer a sign-off."""
    claim_id = claim["claim_id"]
    state = graph.get_state(config)
    if state.values and not state.next:
        return state.values["messages"][-1].text
    if state.next == ("approval",):
        if claim["signed_off_by"] is None:
            return f"{claim_id} is waiting for a handler to sign off."
        start = Command(resume={"handler": claim["signed_off_by"]})
    else:
        start = None if state.next else new_claim(claim_id)
    context = ClaimContext(claim_id, run_id)
    with timing.segment(claim_id, run_id):
        result = graph.invoke(start, config, context=context, durability="sync")
    return result["messages"][-1].text
