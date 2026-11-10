"""The dispatcher: works a run's claims, up to N at once, with no model.

START -> list_claims -> one work_claim for each claim (at most N at a time) -> END.
Each claim saves its own progress, so the dispatcher saves none.
"""

import operator
from functools import partial
from typing import Annotated, TypedDict

from langgraph.errors import NodeError
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy, Send

from agent import agents, api, work
from agent.work import Decide

RETRY = RetryPolicy(initial_interval=5.0, max_attempts=4, retry_on=work.WAIT_AND_RETRY)


class Dispatch(TypedDict):
    """A run, the claims it works, and what each worker reports."""

    run_id: int
    claims: list[str]
    results: Annotated[list[str], operator.add]


class ClaimTask(TypedDict):
    """One claim for one worker."""

    run_id: int
    claim_id: str


def list_claims(state: Dispatch) -> dict[str, list[str]]:
    """List the run's claims, in the order the backend chose them."""
    run = api.get_run(state["run_id"])
    return {"claims": [claim["claim_id"] for claim in run["claims"]]}


def fan_out(state: Dispatch) -> list[Send]:
    """Send each claim to a worker of its own."""
    return [
        Send("work_claim", ClaimTask(run_id=state["run_id"], claim_id=claim_id))
        for claim_id in state["claims"]
    ]


def worker(state: ClaimTask, decide: Decide) -> dict[str, list[str]]:
    """Work one claim and report what happened."""
    return {"results": [work.work_claim(state["run_id"], state["claim_id"], decide)]}


def error_handler(state: ClaimTask, error: NodeError) -> dict[str, list[str]]:
    """Leave a claim in progress when its waits run out; no error stops the run."""
    return {"results": [work.give_up(state["run_id"], state["claim_id"], error.error)]}


def build_dispatcher(
    decide: Decide = agents.decide_claim, retry: RetryPolicy = RETRY
) -> CompiledStateGraph[Dispatch, None, Dispatch, Dispatch]:
    """Build the dispatcher graph; `decide` works one claim."""
    builder = StateGraph(Dispatch)
    builder.add_node("list_claims", list_claims)
    builder.add_node(
        "work_claim",
        partial(worker, decide=decide),
        retry_policy=retry,
        error_handler=error_handler,  # pyright: ignore[reportArgumentType]
    )
    builder.add_edge(START, "list_claims")
    builder.add_conditional_edges("list_claims", fan_out, ["work_claim"])
    builder.add_edge("work_claim", END)
    return builder.compile()


def run_dispatch(
    run_id: int, concurrency: int, decide: Decide = agents.decide_claim
) -> list[str]:
    """Work every claim of a run, `concurrency` at a time, then finish the run."""
    result = build_dispatcher(decide).invoke(
        Dispatch(run_id=run_id, claims=[], results=[]),
        {"max_concurrency": concurrency},
    )
    api.finish_run(run_id)
    return result["results"]
