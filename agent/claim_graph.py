"""The claim agent's graph: its nodes joined by edges, and the checkpointer.

START -> screen -> agent <-> tools, or refer_flagged -> END for a flagged claim.
agent -> settle; settle -> agent (no decision yet), approval (over the limit), pay
(at or under it) or remember (a decline or a referral). pay -> approval when the
Gateway refuses the payment, else remember. approval pauses until a handler signs
off, which pays, and goes on to remember, or, when a handler sends the decision
back, to agent. remember -> END, the last node of every path: the claim is saved to
the customer's memory once its decision is final.
"""

from functools import partial
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from agent import claim_nodes, step_recording
from agent.claim_state import ClaimState
from agent.contexts import ClaimContext
from agent.memory import CustomerMemory
from agent.tools import claim_tools


def after_screen(state: ClaimState) -> Literal["agent", "refer_flagged"]:
    """Refer a claim the check flagged; otherwise the claim agent works it."""
    return "refer_flagged" if state["flagged"] else "agent"


def after_agent(state: ClaimState) -> Literal["tools", "settle"]:
    """Run the tools the model asked for, or move on to the decision."""
    return "tools" if state["messages"][-1].tool_calls else "settle"


def after_settle(
    state: ClaimState,
) -> Literal["agent", "approval", "pay", "remember"]:
    """Send the claim back to the agent until it is decided, then to its payment,
    its sign-off or, for a decline or a referral, to be remembered."""
    if not state["decision"]:
        return "agent"
    if state["decision"] != "approve":
        return "remember"
    return "approval" if state["needs_sign_off"] else "pay"


def after_pay(state: ClaimState) -> Literal["approval", "remember"]:
    """Send a payment the Gateway refused to a sign-off, else on to be remembered."""
    return "approval" if state["needs_sign_off"] else "remember"


def after_approval(state: ClaimState) -> Literal["agent", "remember"]:
    """Send a claim whose decision was sent back to the agent, else remember it."""
    return "remember" if state["decision"] else "agent"


def build_graph(
    checkpointer: BaseCheckpointSaver,
    model: BaseChatModel,
    instructions: str,
    screening_model: BaseChatModel,
    memory: CustomerMemory | None,
) -> CompiledStateGraph[ClaimState, ClaimContext, ClaimState, ClaimState]:
    """Build the claim graph on a checkpointer.

    With a memory the agent also has a tool to search it, and the decided claim is
    saved to it at the end; with none, the graph's `remember` node does nothing.
    """
    tools = claim_tools(memory is not None)
    builder = StateGraph(ClaimState, context_schema=ClaimContext)
    builder.add_node("screen", partial(claim_nodes.screen, model=screening_model))
    builder.add_node("refer_flagged", claim_nodes.refer_flagged)
    builder.add_node(
        "agent",
        partial(
            claim_nodes.agent,
            model=model.bind_tools(tools),
            instructions=instructions,
        ),
    )
    builder.add_node(
        "tools",
        ToolNode(
            tools,
            handle_tool_errors=False,
            wrap_tool_call=step_recording.record_tool_call,
        ),
    )
    builder.add_node("settle", claim_nodes.settle)
    builder.add_node("remember", partial(claim_nodes.remember, memory=memory))
    builder.add_node("approval", claim_nodes.approval)
    builder.add_node("pay", claim_nodes.pay)

    builder.add_edge(START, "screen")
    builder.add_conditional_edges("screen", after_screen, ["agent", "refer_flagged"])
    builder.add_edge("refer_flagged", END)
    builder.add_conditional_edges("agent", after_agent, ["tools", "settle"])
    builder.add_edge("tools", "agent")
    builder.add_conditional_edges(
        "settle", after_settle, ["agent", "approval", "pay", "remember"]
    )
    builder.add_conditional_edges("pay", after_pay, ["approval", "remember"])
    builder.add_conditional_edges("approval", after_approval, ["agent", "remember"])
    builder.add_edge("remember", END)
    return builder.compile(checkpointer=checkpointer)
