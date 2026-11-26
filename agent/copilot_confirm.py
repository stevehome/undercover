"""The pause before a sign-off: checks in code, then asks the handler.

The node checks that the handler may sign off that claim and that it is waiting for
one, and declines in code if not, with no card and no pause. Otherwise it reads the
claim, the customer, the payout and the agent's reason from our records, never from
what the model wrote, and pauses with them as a card. Code before `interrupt` runs
again when the handler answers, so it only reads; nothing is written before the
pause. The sign-off itself is left to the tools node, whose tool refuses without the
confirmation this node records.
"""

from typing import Any

from langgraph.runtime import Runtime
from langgraph.types import interrupt

from agent import copilot_api
from agent.copilot_context import CopilotContext
from agent.copilot_state import CopilotState
from agent.refusals import Refusal

SIGN_OFF = "sign_off_claim"
WAITING_FOR_SIGN_OFF = "waiting for sign-off"
CANCELLED = "The handler cancelled. Nothing was signed off."
CHANGED = "The claim changed after you were asked, so nothing was signed off."


def _declined(note: str) -> dict[str, Any]:
    return {"confirmed": "", "sign_off_note": note}


def _card(context: CopilotContext, claim: dict[str, Any]) -> dict[str, Any]:
    """The confirmation card, from our records."""
    customer = copilot_api.get_customer(context.sign_in, claim["customer_id"])
    return {
        "kind": "sign_off",
        "claim_id": claim["claim_id"],
        "customer": {"customer_id": customer["customer_id"], "name": customer["name"]},
        "payout": claim["payout"],
        "reason": claim["reason"],
    }


def confirm(state: CopilotState, runtime: Runtime[CopilotContext]) -> dict[str, Any]:
    """Pause for the handler's answer to a sign-off; the first one in the reply only."""
    context = runtime.context
    calls = [c for c in state["messages"][-1].tool_calls if c["name"] == SIGN_OFF]
    claim_id = calls[0]["args"]["claim_id"]
    if not context.can_approve_over_limit:
        return _declined(
            f"{context.handler_name} can't sign off payouts over the approval limit: "
            "only a handler who can sign them off can"
        )
    try:
        claim = copilot_api.get_claim(context.sign_in, claim_id)
    except Refusal as refusal:
        return _declined(refusal.detail)
    if claim["status"] != WAITING_FOR_SIGN_OFF:
        return _declined(f"{claim_id} isn't waiting for a sign-off: {claim['status']}")
    card = _card(context, claim)
    answer = interrupt(card)
    if answer["card"] != card:
        return _declined(CHANGED)
    if not answer["confirmed"]:
        return _declined(CANCELLED)
    return {"confirmed": claim_id, "sign_off_note": ""}
