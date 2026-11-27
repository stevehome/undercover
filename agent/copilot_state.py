"""What the Copilot's graph keeps for a conversation, saved after every step."""

from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage
from langgraph.graph.message import add_messages


class CopilotState(TypedDict):
    """The conversation, what the memory gave this turn, and this turn's model calls
    and cost, which each turn starts again from nothing, the payment the handler has
    confirmed (the tool and the claim), and why a payment was declined."""

    messages: Annotated[list, add_messages]
    remembered: list[str]
    model_calls: int
    cost_nanos: int
    confirmed: str
    sign_off_note: str


def new_turn(message: str) -> CopilotState:
    """Return what a turn starts with: the handler's message and nothing counted."""
    return {
        "messages": [HumanMessage(message)],
        "remembered": [],
        "model_calls": 0,
        "cost_nanos": 0,
        "confirmed": "",
        "sign_off_note": "",
    }
