"""The nodes of the claim graph: each takes the state and returns what it changes."""

from decimal import Decimal
from typing import Any

from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from agent import api, screening
from agent.api import GATEWAY_HOLD, WAITING_FOR_SIGN_OFF
from agent.claim_state import ClaimState
from agent.contexts import ClaimContext
from agent.refusals import BY_GATEWAY, Refusal
from agent.tool_route import APP

MAX_MODEL_CALLS = 30
SECURITY_CHECK = "Security check"


class ModelCallLimit(Exception):  # noqa: N818 - a failure of the claim
    """The model was called more times than a claim should ever need."""


def screen(
    state: ClaimState, runtime: Runtime[ClaimContext], *, model: BaseChatModel
) -> dict[str, Any]:
    """Check the claim for instructions hidden in it, and record what was found.

    A node saves when it finishes, so a claim carried on later is not checked again.
    """
    claim_id = runtime.context.claim_id
    claim = api.get_claim(claim_id)
    found = screening.screen(model, claim, runtime.context.run_id)
    if found.instructions_found:
        api.record_step(claim_id, f"Security check: {found.reason}")
        return {"flagged": found.reason}
    api.record_step(claim_id, "Security check: no instructions found")
    return {"flagged": ""}


def refer_flagged(state: ClaimState, runtime: Runtime[ClaimContext]) -> dict[str, Any]:
    """Refer a flagged claim to a handler without the claim agent seeing it."""
    claim_id = runtime.context.claim_id
    reason = f"The security check found an instruction in the claim. {state['flagged']}"
    api.decide_claim(claim_id, "refer", Decimal(0), reason, SECURITY_CHECK)
    api.record_step(claim_id, f"Referred to a handler: {reason}")
    return {"messages": [AIMessage(reason)]}


def agent(
    state: ClaimState,
    runtime: Runtime[ClaimContext],
    *,
    model: Runnable[LanguageModelInput, AIMessage],
    instructions: str,
) -> dict[str, Any]:
    """Call the model with the conversation so far, and record what it cost."""
    if state["model_calls"] >= MAX_MODEL_CALLS:
        raise ModelCallLimit(f"More than {MAX_MODEL_CALLS} model calls on one claim")
    reply = model.invoke([SystemMessage(instructions), *state["messages"]])
    api.record_model_call(
        runtime.context.claim_id,
        runtime.context.run_id,
        reply.response_metadata["model_name"],
        reply.response_metadata["token_usage"],
    )
    return {"messages": [reply], "model_calls": state["model_calls"] + 1}


def settle(state: ClaimState, runtime: Runtime[ClaimContext]) -> dict[str, Any]:
    """Read the decision back from the backend, which says if it needs a sign-off."""
    claim_id = runtime.context.claim_id
    claim = api.get_claim(claim_id)
    if claim["decision"] is None:
        reminder = HumanMessage(
            "No decision is recorded yet. Record it with decide_claim."
        )
        return {"messages": [reminder], "decision": ""}
    needs_sign_off = claim["status"] == WAITING_FOR_SIGN_OFF
    if needs_sign_off:
        api.record_step(
            claim_id, f"Waiting for a handler to sign off ${claim['payout']}"
        )
    return {
        "decision": claim["decision"],
        "payout": claim["payout"],
        "needs_sign_off": needs_sign_off,
    }


def approval(state: ClaimState, runtime: Runtime[ClaimContext]) -> dict[str, Any]:
    """Wait for a handler's sign-off, which pays. Code before `interrupt` runs twice."""
    answer = interrupt(
        {"claim_id": runtime.context.claim_id, "payout": state["payout"]}
    )
    api.record_step(runtime.context.claim_id, f"Signed off by {answer['handler']}")
    return {}


def pay(state: ClaimState, runtime: Runtime[ClaimContext]) -> dict[str, Any]:
    """Pay the claim through the route; the backend treats a repeat as done.

    A payment the Gateway's Policy refuses leaves the claim waiting for a handler's
    sign-off, which pays it.
    """
    context = runtime.context
    claim_id = context.claim_id
    amount = Decimal(state["payout"])
    try:
        context.route.call(APP, "pay_claim", {"claim_id": claim_id, "amount": amount})
    except Refusal as refusal:
        if refusal.source != BY_GATEWAY:
            raise
        api.record_step(claim_id, refusal.message)
        api.hold_for_sign_off(claim_id, GATEWAY_HOLD)
        api.record_step(claim_id, f"Waiting for a handler to sign off ${amount}")
        return {}
    api.record_step(claim_id, f"Paid ${state['payout']}")
    return {}
