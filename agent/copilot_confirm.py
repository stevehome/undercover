"""The pause before a payment: checks in code, then asks the handler.

The node serves the two payments a handler confirms: signing off a held payout and
paying an upheld appeal's redress. It checks that the handler may make the payment
and that it can be made, and declines in code if not, with no card and no pause.
Otherwise it reads what the card shows from our records, never from what the model
wrote, and pauses with it. Code before `interrupt` runs again when the handler
answers, so it only reads; nothing is written before the pause. The payment itself
is left to the tools node, whose tool refuses without the confirmation this node
records.
"""

from typing import Any

from langgraph.runtime import Runtime
from langgraph.types import interrupt

from agent import copilot_api
from agent.copilot_context import CopilotContext
from agent.copilot_state import CopilotState
from agent.refusals import Refusal

SIGN_OFF = "sign_off_claim"
PAY_REDRESS = "pay_redress"
PAYMENTS = (SIGN_OFF, PAY_REDRESS)
WAITING_FOR_SIGN_OFF = "waiting for sign-off"
UPHELD = "upheld"
ONE_AT_A_TIME = "One payment at a time: ask again for this one after the first."
CANCELLED = {
    SIGN_OFF: "The handler cancelled. Nothing was signed off.",
    PAY_REDRESS: "The handler cancelled. Nothing was paid.",
}
CHANGED = {
    SIGN_OFF: "The claim changed after you were asked, so nothing was signed off.",
    PAY_REDRESS: "The appeal changed after you were asked, so nothing was paid.",
}


class Declined(Exception):  # noqa: N818 - a reason the handler is told, not a failure
    """A payment that can't be made, with the reason to tell the handler."""


def confirmation_key(tool: str, claim_id: str) -> str:
    """What the state holds once the handler has confirmed this payment."""
    return f"{tool}:{claim_id}"


def _sign_off_card(context: CopilotContext, claim_id: str) -> dict[str, Any]:
    """The card for a sign-off, or `Declined`."""
    if not context.can_approve_over_limit:
        raise Declined(
            f"{context.handler_name} can't sign off payouts over the approval limit: "
            "only a handler who can sign them off can"
        )
    try:
        claim = copilot_api.get_claim(context.sign_in, claim_id)
    except Refusal as refusal:
        raise Declined(refusal.detail) from refusal
    if claim["status"] != WAITING_FOR_SIGN_OFF:
        raise Declined(f"{claim_id} isn't waiting for a sign-off: {claim['status']}")
    customer = copilot_api.get_customer(context.sign_in, claim["customer_id"])
    return {
        "kind": "sign_off",
        "claim_id": claim_id,
        "customer": {"customer_id": customer["customer_id"], "name": customer["name"]},
        "payout": claim["payout"],
        "reason": claim["reason"],
    }


def _redress_card(context: CopilotContext, claim_id: str) -> dict[str, Any]:
    """The card for paying redress, or `Declined`.

    It is read as a model reads an appeal, so a marked appeal's reason is left out.
    """
    if not context.can_approve_over_limit:
        raise Declined(
            f"{context.handler_name} can't pay redress: only a handler who can "
            "sign off payouts over the approval limit can"
        )
    try:
        appeal = copilot_api.get_appeal(context.sign_in, claim_id)
    except Refusal as refusal:
        raise Declined(refusal.detail) from refusal
    if appeal["status"] != UPHELD:
        raise Declined(f"{claim_id}'s appeal isn't upheld: it is {appeal['status']}")
    if appeal["redress_payment"] is not None:
        raise Declined(f"The redress on {claim_id} has already been paid")
    return {
        "kind": "redress",
        "claim_id": claim_id,
        "customer": appeal["claim"]["customer"],
        "redress": appeal["redress"],
        "reason": appeal["ombudsman_reason"],
    }


CARDS = {SIGN_OFF: _sign_off_card, PAY_REDRESS: _redress_card}


def _declined(note: str) -> dict[str, Any]:
    return {"confirmed": "", "sign_off_note": note}


def confirm(state: CopilotState, runtime: Runtime[CopilotContext]) -> dict[str, Any]:
    """Pause for the handler's answer to a payment; the first one in the reply only."""
    call = next(c for c in state["messages"][-1].tool_calls if c["name"] in PAYMENTS)
    tool, claim_id = call["name"], call["args"]["claim_id"]
    try:
        card = CARDS[tool](runtime.context, claim_id)
    except Declined as declined:
        return _declined(str(declined))
    answer = interrupt(card)
    if answer["card"] != card:
        return _declined(CHANGED[tool])
    if not answer["confirmed"]:
        return _declined(CANCELLED[tool])
    return {"confirmed": confirmation_key(tool, claim_id), "sign_off_note": ""}
