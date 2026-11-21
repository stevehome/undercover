"""The UnderCover Agent: decides one claim, or carries it on."""

from contextvars import Context
from typing import Any, NamedTuple

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command

from agent import api, checkpoint, harness, lease, memory, routes, timing, tracing
from agent.claim_graph import build_graph
from agent.claim_state import new_claim
from agent.contexts import ClaimContext
from agent.memory import CustomerMemory

DECIDED_BY = "UnderCover Agent, configuration version"


class Attempt(NamedTuple):
    """What one working of a claim is recorded with and uses: its thread, run, tags,
    maker and memory."""

    thread_id: str
    run_id: int | None
    tags: list[str]
    decided_by: str
    memory: CustomerMemory | None


def decide_claim(
    claim_id: str,
    llm: BaseChatModel | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    run_id: int | None = None,
    screening_llm: BaseChatModel | None = None,
) -> str:
    """Work a claim through its graph: from the start, or from where it stopped.

    `run_id` is the run the work and its cost are recorded with, if any. The
    claim agent is built from the run's version of the configuration, or from the
    current version when there is no run.

    It runs in a fresh context, so a claim worked in a dispatch has a trace of
    its own, tagged with the run.

    The claim is checked for hidden instructions first, by `screening_llm` (the
    check's own model when there is none), and one that has any goes to a handler.

    The model's tools and the payment take the route chosen when the claim's context
    is built: the Gateway's when `UNDERCOVER_GATEWAY_URL` is set, else direct.

    A claim waiting at its sign-off carries on only once a handler has signed off.
    A claim another agent is working is left to that agent.

    An evaluation's claim is never signed off, so once it is worked its saved
    progress is cleared, even if it is held for a sign-off.
    """
    with lease.held(claim_id) as free:
        if not free:
            return f"{claim_id} is being worked by another agent."
        claim = api.get_claim(claim_id)
        thread_id = f"{claim_id}-{claim['thread']}"
        saver = checkpointer or checkpoint.saver()
        configuration = (
            api.current_configuration()
            if run_id is None
            else api.run_configuration(run_id)
        )
        llm = llm or harness.model(harness.model_settings(configuration))
        customer_memory = memory.open_for(claim)
        graph = build_graph(
            saver,
            llm,
            configuration["instructions"],
            screening_llm or harness.screening_model(),
            customer_memory,
        )
        attempt = Attempt(
            thread_id,
            run_id,
            _tags(run_id, configuration["round_id"]),
            f"{DECIDED_BY} {configuration['version']}",
            customer_memory,
        )
        outcome = Context().run(_work_traced, graph, claim, attempt)
        if claim["evaluation_run_id"] is not None:
            saver.delete_thread(thread_id)
        return outcome


def _tags(run_id: int | None, round_id: int | None) -> list[str]:
    """The tags that find a run's claims together, and a round's as well."""
    run_tags = [] if run_id is None else [f"run-{run_id}"]
    return [*run_tags, *([] if round_id is None else [f"round-{round_id}"])]


def _work_traced(graph: Any, claim: dict[str, Any], attempt: Attempt) -> str:
    """Work a claim in a trace of its own, in one Langfuse session."""
    with tracing.trace(attempt.thread_id, attempt.tags) as traced:
        thread = {"thread_id": attempt.thread_id}
        config: RunnableConfig = {**traced, "configurable": thread}
        return _work(graph, config, claim, attempt)


def _work(
    graph: Any, config: RunnableConfig, claim: dict[str, Any], attempt: Attempt
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
    context = ClaimContext(
        claim_id,
        claim["customer_id"],
        attempt.run_id,
        attempt.decided_by,
        routes.choose(),
        attempt.memory,
    )
    with timing.segment(claim_id, attempt.run_id):
        result = graph.invoke(start, config, context=context, durability="sync")
    return result["messages"][-1].text
